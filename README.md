![Logo](https://whitesource-resources.s3.amazonaws.com/ws-sig-images/Whitesource_Logo_178x44.png)  

[![License](https://img.shields.io/badge/License-Apache%202.0-yellowgreen.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub release](https://img.shields.io/github/v/release/whitesource-ps/ws-policy-report)](https://github.com/whitesource-ps/ws-policy-report/releases/latest)    
[![Build and Publish](https://github.com/whitesource-ps/ws-policy-report/actions/workflows/ci.yml/badge.svg)](https://github.com/whitesource-ps/ws-policy-report/actions/workflows/ci.yml)
[![Python 3.6](https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Blue_Python_3.6%2B_Shield_Badge.svg/86px-Blue_Python_3.6%2B_Shield_Badge.svg.png)](https://www.python.org/downloads/release/python-360/)

# WhiteSource Policy Report
The script enables retrieving all policies for each project in a single WhiteSource organization.

### What does the script do?
For each project, the script fetches all project's policies, its parent product's policies, and the organization policies this project belongs to.
In addition, it indicates whether a policy is enabled or disabled.
The report will be presented in Excel format.

### Supported Operating Systems
- **Linux (Bash):**	CentOS, Debian, Ubuntu, RedHat
- **Windows (PowerShell):**	10, 2012, 2016

### Prerequisites
- Python 3.6 or above.

### Installation
1. Download and unzip **ws-policy-report.zip**.
2. From the command line, navigate to the ws-policy-report directory and install the package:  
   `pip install -r requirements.txt`. 
3. Edit the `/policy_report/params.config` file and update the relevant parameters (see the configuration parameters below) or
   use a cmd line for running the `/policy_report/ws_policy_report.py` script.
    
### Configuration Parameters'
```
====================================================================================================================================================================================
| config file             | cli                             | Environment Variables          | Default  | Description                                                              |
====================================================================================================================================================================================
| wsUrl                   | -u,  --wsUrl                    | WSPR_WS_URL                    |          | WhiteSource application page >Home >Admin >Integration >Server URL       |
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
| userKey                 | -k,  --userKey                  | WSPR_USER_KEY                  |          | WhiteSource application page >Profile >User Keys                         |
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
| orgToken                | -t,  --orgToken                 | WSPR_ORG_TOKEN                 |          | WhiteSource application page >Home >Integrate tab >Organization >API Key |
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
| projectParallelismLevel | -m,  --projectParallelismLevel  | WSPR_PROJECT_PARALLELISM_LEVEL |    9     | Number of threads to run API calls (max number = 20)                     |
====================================================================================================================================================================================
```
### Execution
 From the command line:
 `python ws_policy_report.py -u $wsUrl -k $userKey -t $orgToken -m $projectParallelismLevel`
 
 Using a config file:
 `python ws_policy_report.py -c / --configFile <CONFIG_FILE>`
 
 Environment Variables:
 - A parameter name, as it is defined in the configuration file, is converted to upper case with underscore (`_`) separators, and **WSPR**_ prefix is added.
 - For example, the `fileName` parameter can be set using the `WSPR_FILE_NAME` environment variable.
 - In case an environment variable exists, it will overrun any value which is defined for the matching parameter in the command line/configuration file.

### Output
 An Excel file in the following format:
 `policy_report_YYYY-MM-DD_hh-mm-ss.xlsx`
 
### Author
WhiteSource Software ©
