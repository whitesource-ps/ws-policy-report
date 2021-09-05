import argparse
import concurrent
import json
import logging
import os
import string
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from configparser import ConfigParser
from datetime import datetime
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import requests
import xlsxwriter

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(asctime)s %(thread)d: %(message)s', stream=sys.stdout)

DEFAULT_CONFIG_FILE = 'params.config'
CONFIG_FILE_HEADER_NAME = 'DEFAULT'

WSPR_PREFIX = 'WSPR_'
WSPR_ENV_VARS = [WSPR_PREFIX + sub for sub in ('WS_URL', 'USER_KEY', 'ORG_TOKEN', 'PROJECT_PARALLELISM_LEVEL')]

agent_info = 'agentInfo'
PS = 'ps-'
AGENT_NAME = 'policy-report'
AGENT_VERSION = '0.1.0'

agent_info_details = {'agent': PS + AGENT_NAME, 'agentVersion': AGENT_VERSION}

get_product_project_details = 'getProductProjectVitals'
get_org_details = 'getOrganizationDetails'
get_org_product_vitals = 'getOrganizationProductVitals'
get_org_project_vitals = 'getOrganizationProjectVitals'
get_project_policies = 'getProjectPolicies'
aggregate_policies = 'aggregatePolicies'

REQUEST_TYPE = 'requestType'
USER_KEY = 'userKey'
PROJECT_TOKEN = 'projectToken'
PRODUCT_TOKEN = 'productToken'
ORG_TOKEN = 'orgToken'
api_version = '/api/v1.3'
WS_URL = 'wsUrl'
config = dict()
org_name_for_excel_output = ''
PROJECT_PARALLELISM_LEVEL = 'projectParallelismLevel'
PROJECT_PARALLELISM_LEVEL_MAX_VALUE = 20
PROJECT_PARALLELISM_LEVEL_DEFAULT_VALUE = 9
PROJECT_PARALLELISM_LEVEL_RANGE = list(range(1, PROJECT_PARALLELISM_LEVEL_MAX_VALUE + 1))

WS_LOGO_URL = 'https://whitesource-resources.s3.amazonaws.com/ws-sig-images/Whitesource_Logo_178x44.png'


class Row:
    def __init__(self):
        self.project_name = ''
        self.project_policies = []
        self.product_name = ''
        self.product_policies = []
        self.org_name = ''
        self.org_policies = []


def get_org_projects_polices_aggregated_data():
    # 1. Retrieve org name
    org_details = post_request(get_org_details, ORG_TOKEN, config['org_token'], {})
    org_name = org_details['orgName']

    # 2. Retrieve product tokens and names
    org_products_vitals = post_request(get_org_product_vitals, ORG_TOKEN, config['org_token'], {})
    products_tokens_and_products_names = get_scope_tokens_and_name_from_vitals(org_products_vitals)

    # 3. Retrieve project tokens and names
    org_projects_vitals = post_request(get_org_project_vitals, ORG_TOKEN, config['org_token'], {})
    projects_tokens_and_projects_names = get_scope_tokens_and_name_from_vitals(org_projects_vitals)

    # 4. Map projects tokens and its parent product name
    products_names_and_projects = get_products_names_and_projects(products_tokens_and_products_names)
    projects_tokens_products_names = get_projects_tokens_products_names(products_names_and_projects)

    # 5. Run API for org_projects_policies_aggregated : getProjectPolicies , aggregate_policies: 'true'
    policies = get_policies(org_projects_vitals)

    return build_records(org_name, policies, projects_tokens_and_projects_names, projects_tokens_products_names)


def get_products_names_and_projects(products_tokens_and_products_names):
    products_names_and_projects = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=int(config['project_parallelism_level'])) as executor:
        response = {executor.submit(get_product_project_vitals, product_token): product_name for product_token, product_name in products_tokens_and_products_names.items()}

        for future in concurrent.futures.as_completed(response):
            key = response[future]
            value = future.result()
            products_names_and_projects.update({key: value})

    return products_names_and_projects


def get_projects_tokens_products_names(products_names_and_projects):
    projects_tokens_products_names = {}
    for product_name, projects in products_names_and_projects.items():
        for project in projects['projectVitals']:
            projects_tokens_products_names.update({project['token']: product_name})
    return projects_tokens_products_names


def get_policies(org_projects_vitals):
    policies = []
    with ThreadPoolExecutor(max_workers=int(config['project_parallelism_level'])) as executor:
        response = {executor.submit(get_org_projects_policies_aggregated, project['token'], project['name']): [project['token'], project['name']] for project in org_projects_vitals['projectVitals']}
        for future in concurrent.futures.as_completed(response):
            policies.append(future.result())
    return policies


def build_records(org_name, res_all_policies, projects_tokens_and_projects_names, map_projects_tokens_to_products_names):
    global org_name_for_excel_output
    org_name_for_excel_output = org_name
    project_instance = []
    for project in res_all_policies:
        row_inst = Row()
        row_inst.project_name = projects_tokens_and_projects_names[project['project_token']]
        row_inst.product_name = map_projects_tokens_to_products_names[project['project_token']]
        row_inst.org_name = org_name
        project_policies = project['policies']

        for policy in project_policies:
            policy_scope = policy['policyContext']
            policy_details = policy['name'] + '(' + policy['owner']['name'] + ',' + policy['owner']['email'] + ',' + policy['creationTime'] + ')' + ' - Status: ' + ('Enabled' if policy['enabled'] else 'Disabled')
            if policy_scope == 'DOMAIN':
                row_inst.org_policies.append(policy_details)
            elif policy_scope == 'PRODUCT':
                row_inst.product_policies.append(policy_details)
            elif policy_scope == 'PROJECT':
                row_inst.project_policies.append(policy_details)

        row_inst_dict = vars(row_inst)
        row_inst_new_dict = {}

        # convert policies
        for key, value in row_inst_dict.items():
            if type(value) == list:  # convert policies from lists to strings
                row_inst_new_dict[key] = '\n'.join(value)
            else:
                row_inst_new_dict[key] = value

        project_instance.append(row_inst_new_dict)

    return project_instance


# ================= API calls section Start =================

def get_product_project_vitals(product_token):
    response = post_request(get_product_project_details, PRODUCT_TOKEN, product_token, {})
    return response


def get_org_projects_policies_aggregated(project_token, project_name):
    logging.info(f'getting aggregated policies for project token : {project_token} ,project name : {project_name}')

    response = post_request(get_project_policies, PROJECT_TOKEN, project_token, {aggregate_policies: 'true'})
    response['project_token'] = project_token
    return response


def post_request(request_type, token_type, token, additional_values):
    logging.debug("Using '%s' API", request_type)
    headers = {'Content-Type': 'application/json', 'Accept-Charset': 'utf-8'}
    body = {agent_info: agent_info_details,
            REQUEST_TYPE: request_type,
            USER_KEY: config['user_key'],
            token_type: token}
    body.update(additional_values)
    body2string = json.dumps(body)
    response_beta = requests.post(config['ws_url'] + api_version, data=body2string.encode('utf-8'), headers=headers)
    logging.debug("Finish using '%s' API", request_type)
    response_object = json.loads(response_beta.text)
    check_errors_in_response(response_object)
    return response_object


def check_errors_in_response(response):
    error = False
    if 'errorCode' in response:
        logging.error('Error code: %s', response['errorCode'])
        error = True
    if 'errorMessage' in response:
        if 'occupied' in response['errorMessage']:
            error = False
        else:
            logging.error('Error message: %s', response['errorMessage'])
            error = True
    if error:
        logging.error('Status: FAILURE')
        sys.exit(1)


# ================= API calls section End =================

def get_scope_tokens_and_name_from_vitals(scope_vitals):
    scope_tokens_and_names = {}
    scope_vitals_list = list(scope_vitals.values())
    for scope in scope_vitals_list[0]:
        element_key = scope['token']
        element_value = scope['name']
        scope_tokens_and_names.update({element_key: element_value})

    return scope_tokens_and_names


def create_excel_report(data):
    file_name = 'policy_report'
    xlsx = '.xlsx'
    logging.info('Start generating policy report...')
    now = datetime.now()
    workbook = xlsxwriter.Workbook(file_name + now.strftime('_%Y-%m-%d_%H-%M-%S') + xlsx)
    worksheet = workbook.add_worksheet('Policies')

    # WorkbookFormats
    header_cell_format = workbook.add_format({'bold': True, 'italic': False, 'align': 'left', 'valign': 'top', 'text_wrap': True})
    body_cell_format = workbook.add_format({'align': 'left', 'valign': 'top', 'text_wrap': True})
    sign_cell_format = workbook.add_format({'align': 'left', 'valign': 'top', 'text_wrap': False})
    date_format = workbook.add_format({'num_format': 'dd/MM/yyyy HH:mm:ss', 'align': 'left', 'valign': 'top', 'text_wrap': False})

    # Create table header
    worksheet_headers = list(vars(Row()).keys())
    header_row_number = 4
    for field in worksheet_headers:
        col = worksheet_headers.index(field)
        field = string.capwords(field.replace('_', ' '))  # remove under score and Upper case first letters
        worksheet.write(header_row_number, col, field, header_cell_format)

    # Create table row and insert data
    table_row = header_row_number + 1
    worksheet.freeze_panes(table_row, 0)
    for record in data:
        for key, value in record.items():
            col = worksheet_headers.index(key)
            worksheet.write(table_row, col, value, body_cell_format)
        table_row += 1

    # align the report cells
    ws_entity_column = ('A', 'C', 'E')
    ws_policies_column = ('B', 'D', 'F')

    for entity_column, policies_column in zip(ws_entity_column, ws_policies_column):
        entity_column_width = (20 if entity_column in ws_entity_column else 0)
        policies_column_width = (80 if policies_column in ws_policies_column else 0)
        worksheet.set_column(f'{entity_column}:{entity_column}', entity_column_width, body_cell_format)
        worksheet.set_column(f'{policies_column}:{policies_column}', policies_column_width, body_cell_format)

    # Read an WhiteSource logo image from a remote url.
    try:
        image_data = BytesIO(urlopen(WS_LOGO_URL).read())
    except HTTPError as e:
        logging.error('Error code: ', e.code)
    except URLError as e:
        logging.error('Reason: ', e.reason)
    else:
        worksheet.insert_image('A2', WS_LOGO_URL, {'image_data': image_data, 'x_scale': 0.8, 'y_scale': 0.8, 'object_position': 1})

    # Add WhiteSource description
    worksheet.write_string(table_row + 2, 0, 'Report was generated by WhiteSource Software ©', sign_cell_format)

    # Report timestamp
    worksheet.write_datetime(table_row + 3, 0, now, date_format)
    workbook.close()
    logging.info(f'Successfully generated report for the organization - {org_name_for_excel_output} at: {file_name}')


def get_args(arguments) -> dict:
    """Get configuration arguments"""

    logging.info('Start analyzing arguments.')
    parser = argparse.ArgumentParser(description='policy-report parser')

    parser.add_argument('-c', '--configFile', help='The config file', required=False, dest='conf_f')
    is_config_file = bool(arguments[0] in ['-c', '--configFile'])

    parser.add_argument('-u', '--' + WS_URL, help='The organization url', required=not is_config_file, dest='ws_url')
    parser.add_argument('-k', '--' + USER_KEY, help='The admin user key', required=not is_config_file, dest='user_key')
    parser.add_argument('-t', '--' + ORG_TOKEN, help='The organization token', required=not is_config_file, dest='org_token')
    parser.add_argument('-m', '--' + PROJECT_PARALLELISM_LEVEL, help='The number of threads to run with', required=not is_config_file, dest='project_parallelism_level', type=int, default=PROJECT_PARALLELISM_LEVEL_DEFAULT_VALUE, choices=PROJECT_PARALLELISM_LEVEL_RANGE)

    args = parser.parse_args()

    if args.conf_f is None:
        args_dict = vars(args)
        args_dict.update(get_config_parameters_from_environment_variables())

    elif os.path.exists(args.conf_f):
        logging.info(f'Using {args.conf_f} , additional arguments from the CLI will be ignored')
        args_dict = get_config_file(args.conf_f)
    else:
        logging.error("Config file doesn't exists")
        sys.exit(1)

    logging.info('Finished analyzing arguments.')
    return args_dict


def get_config_file(config_file) -> dict:
    conf_file = ConfigParser()
    conf_file.read(config_file)

    logging.info('Start analyzing config file.')
    conf_file_dict = {
        'ws_url': conf_file[CONFIG_FILE_HEADER_NAME].get('wsUrl'),
        'user_key': conf_file[CONFIG_FILE_HEADER_NAME].get(USER_KEY),
        'org_token': conf_file[CONFIG_FILE_HEADER_NAME].get(ORG_TOKEN),
        'project_parallelism_level': conf_file[CONFIG_FILE_HEADER_NAME].getint(PROJECT_PARALLELISM_LEVEL, fallback=PROJECT_PARALLELISM_LEVEL_DEFAULT_VALUE)
    }

    check_if_config_project_parallelism_level_is_valid(conf_file_dict['project_parallelism_level'])

    conf_file_dict.update(get_config_parameters_from_environment_variables())

    for key, value in conf_file_dict.items():
        if value is None:
            logging.error(f'Please check your {key} parameter-it is missing from the config file')
            sys.exit(1)

    logging.info('Finished analyzing the config file.')

    return conf_file_dict


def get_config_parameters_from_environment_variables() -> dict:
    os_env_variables = dict(os.environ)
    wspr_env_vars_dict = {}
    for variable in WSPR_ENV_VARS:
        if variable in os_env_variables:
            logging.info(f'found {variable} environment variable - will use its value')
            wspr_env_vars_dict[variable[len(WSPR_PREFIX):].lower()] = os_env_variables[variable]

            if variable == 'WSPR_PROJECT_PARALLELISM_LEVEL':
                check_if_config_project_parallelism_level_is_valid(wspr_env_vars_dict['project_parallelism_level'])

    return wspr_env_vars_dict


def check_if_config_project_parallelism_level_is_valid(parallelism_level):
    if int(parallelism_level) not in PROJECT_PARALLELISM_LEVEL_RANGE:
        logging.error(f'The selected {PROJECT_PARALLELISM_LEVEL} <{parallelism_level}> is not valid')
        sys.exit(1)


def read_setup():
    """reads the configuration from cli / config file and updates in a global config."""

    global config
    args = sys.argv[1:]
    if len(args) > 0:
        config = get_args(args)
    elif os.path.isfile(DEFAULT_CONFIG_FILE):  # used when running the script from an IDE -> same path of CONFIG_FILE (params.config)
        config = get_config_file(DEFAULT_CONFIG_FILE)
    else:
        config = get_config_parameters_from_environment_variables()


def main():
    read_setup()
    projects_policies = get_org_projects_polices_aggregated_data()
    create_excel_report(projects_policies)


if __name__ == '__main__':
    main()
