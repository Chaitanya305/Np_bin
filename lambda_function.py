import boto3
#import os
#import numpy as np
#from datetime import datetime, timedelta, timezone
#from previous_generation_instnce import previous_generation_instance_types, previous_generation_db_instance_types

from ec2 import check_ec2


ec2 = boto3.client('ec2')
sts = boto3.client('sts')
#ag =  boto3.client('autoscaling')
#cloudwatch = boto3.client('cloudwatch')
#rds = boto3.client('rds')

region = ec2.meta.region_name
#region = os.environ['AWS_REGION']
account_id = sts.get_caller_identity()['Account']

def lambda_handler(event, context):

    print('******************* check for EC2 **************************')
    check_ec2()
    #rds_check()
    #s3_check()
    # print('***********checking for NAT***********************')
    # check_nat()
    # print('***********checking for elasticache***********************')
    # check_elasticcache()
    # print('******************checking for dynamodb***************')
    # check_dynamodb()
    # print('******************checking for opensearch ***************')
    # check_opensearch()
    # print('*******************checking for Lambda*******************')
    # check_lambda()


    print("aws region is: ", region)
    print("aws_account is: ", account_id)    

