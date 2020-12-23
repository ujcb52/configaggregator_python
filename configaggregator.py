import boto3
import os
import json
import logging
import sys
from botocore.exceptions import ClientError
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
session = boto3.Session()

def get_account_list():
    """
    Gets a list of Active AWS Accounts in the Organization.
    This is called if the function is not executed by an Sns trigger and is used
    for periodic scheduling to ensure all accounts are correctly configured, and
    prevent gaps in security from activities like new regions being added or GuardDuty
    being disabled.
    """
    aws_account_dict = dict()
    account_list = []
    #Get list of accounts in org
    orgclient = session.client('organizations',region_name='us-east-1')
    response = orgclient.list_accounts()
    while True:
        for account in response['Accounts']:
            account_list.append(account)

        if 'NextToken' in response:
            response = orgclient.list_accounts(
                NextToken=response['NextToken']
            )
        else:
            break       

    LOGGER.debug(account_list)
    for account in account_list:
        LOGGER.debug(account)
        #Filter out suspended accounts and save valid accounts in a dict
        if account['Status'] == 'ACTIVE':
            accountid = account['Id']
            email = account['Email']
            aws_account_dict.update({accountid:email})
    return aws_account_dict


def assume_role(aws_account_number, role_name):
    """
    Assumes the provided role in each account and returns a Config client
    :param aws_account_number: AWS Account Number
    :param role_name: Role to assume in target account
    :param aws_region: AWS Region for the Client call, not required for IAM calls
    :return: Config client in the specified AWS Account and Region
    """

    # Beginning the assume role process for account
    sts_client = boto3.client('sts')
    # Get the current partition
    partition = sts_client.get_caller_identity()['Arn'].split(":")[1]
    response = sts_client.assume_role(
        RoleArn='arn:{}:iam::{}:role/{}'.format(
            partition,
            aws_account_number,
            role_name
        ),
        RoleSessionName='EnableConfigAggregator'
    )
    # Storing STS credentials
    session = boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken']
    )
    LOGGER.debug("Assumed session for {}.".format(
        aws_account_number
    ))

    return session


def lambda_handler(event, context):
    try:
        LOGGER.debug('REQUEST RECEIVED:\n %s', event)
        LOGGER.debug('REQUEST RECEIVED:\n %s', context)
        session = boto3.session.Session()
        aws_account_dict = dict()
        aws_account_dict = get_account_list()
        session = assume_role(os.environ['master_account'],os.environ['assume_role'])
        configclient = session.client('config')
        updateconfig = configclient.put_configuration_aggregator(
            ConfigurationAggregatorName="LandingZoneAggregator",
            AccountAggregationSources=[
                {
                    'AccountIds': list(aws_account_dict.keys()),
                    'AllAwsRegions': True
                }
            ])
        LOGGER.debug(updateconfig)
    # return(True)
        sendResponse(event, context, responseStatus, responseData)     
    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)        
        responseStatus = 'FAILED'
        responseData = {'Failed': 'Failed to add route tables.'}
        sendResponse(event, context, responseStatus, responseData) 

def sendResponse(event, context, responseStatus, responseData):
    responseBody = {'Status': responseStatus,
                    'Reason': 'See the details in CloudWatch Log Stream: ' + context.log_stream_name,
                    'PhysicalResourceId': context.log_stream_name,
                    'StackId': event['StackId'],
                    'RequestId': event['RequestId'],
                    'LogicalResourceId': event['LogicalResourceId'],
                    'Data': responseData}
    LOGGER.info('RESPONSE BODY:n' + json.dumps(responseBody))
    try:
        req = requests.put(event['ResponseURL'], data=json.dumps(responseBody))
        if req.status_code != 200:
            LOGGER.info(req.text)
            raise Exception('Recieved non 200 response while sending response to CFN.')
        return
    except requests.exceptions.RequestException as e:
        LOGGER.error(e)
        raise


# if __name__ == "__main__":
#     lambda_handler("test", "test")
