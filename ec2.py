import boto3
#import os
import numpy as np
from datetime import datetime, timedelta, timezone
from previous_generation_instnce import previous_generation_instance_types, previous_generation_db_instance_types


from metric_cpu import metrics_check
from metric_cpu import cpu_utilization

ec2 = boto3.client('ec2')
ag =  boto3.client('autoscaling')
cloudwatch = boto3.client('cloudwatch')

stopped_instance = []

#to check instance is part of ASG or not
def standalone_instnace(instance_id):
    response = ag.describe_auto_scaling_instances(InstanceIds=[instance_id])
    if len(response['AutoScalingInstances']) == 0:
        return True
    else:
        return False

#check for network utilization
def network_utilization(instance_id):
    threshold = 100 * 1024  # 100KB
    network_in = metrics_check(instance_id, 'NetworkIn', 'Maximum', 'Bytes', 86400, True, 'AWS/EC2', 'InstanceId')
    network_out = metrics_check(instance_id, 'NetworkOut', 'Maximum', 'Bytes', 86400, True, 'AWS/EC2', 'InstanceId')
    #check for threshold
    if network_in and network_out:
        print(f'max network in value for instnace {instance_id} ', max(network_in))
        print(f'max network out value for {instance_id}', max(network_out))
        if max(network_in) < threshold and max(network_out) < threshold:
            return True
        else:
            return False


#Standalone EC2 instances shouldn't experience very low network activity of Network In/Out less than a specified threshold consistently for more than 3 hours in a day.
def network_usage(instance_id):
    threshold = 100 * 1024  # 100KB
    network_in = metrics_check(instance_id, 'NetworkIn', 'Maximum', 'Bytes', 900, False, 'AWS/EC2', 'InstanceId')
    network_out = metrics_check(instance_id, 'NetworkOut', 'Maximum', 'Bytes', 900, False, 'AWS/EC2', 'InstanceId')
    # Ensure the data points are sorted by timestamp
    sorted_data_points_in = sorted(network_in, key=lambda dp: dp['Timestamp'])
    #print('sorted data pointvalues are: ',sorted_data_points_in)
    sorted_data_points_out = sorted(network_out, key=lambda dp: dp['Timestamp'])
    # Organize datapoints by day
    daily_data_in = {}
    in_network = False
    out_network = False
    for datapoint_in in sorted_data_points_in:
        # Convert timestamp to date (YYYY-MM-DD)
        day = datapoint_in['Timestamp'].date()
        if day not in daily_data_in:
            daily_data_in[day] = []
        daily_data_in[day].append(datapoint_in['Maximum'])
    # Check each day for low activity periods consistently 3hrs
    #print('daily data dict is: ', daily_data)
    for day, data_points in daily_data_in.items():
        low_in_activity_count = 0
        for value in data_points:
            if value < threshold:
                low_in_activity_count += 1
            else:
                low_in_activity_count = 0 
            # Check if low activity occurred for more than 3 hours (12 intervals)
            if low_in_activity_count >= 12:  # 12 data points = 3 hours of 15-minute intervals
                print(f"Low network_in activity for more than 3 hours on {day}.")
            #return True  # Low activity detected for at least one day consistently for 3 hours
                in_network = True
                break   #we can do this
        if in_network:
            break

    daily_data_out = {}
    for datapoint_out in sorted_data_points_out:
        # Convert timestamp to date (YYYY-MM-DD)
        day = datapoint_out['Timestamp'].date()
        if day not in daily_data_out:
            daily_data_out[day] = []
        daily_data_out[day].append(datapoint_out['Maximum'])
    # Check each day for low activity periods consistently 3hrs
    #print('daily data dict is: ', daily_data)
    for day, data_points in daily_data_out.items():
        low_out_activity_count = 0
        for value in data_points:
            if value < threshold:
                low_out_activity_count += 1
            else:
                low_out_activity_count = 0 
            # Check if low activity occurred for more than 3 hours (12 intervals)
            if low_out_activity_count >= 12:  # 12 data points = 3 hours of 15-minute intervals
                print(f"Low network_out activity for more than 3 hours on {day}.")
                #return True  # Low activity detected for at least one day consistently for 3 hours
                out_network = True
                break  #we can do 
        if out_network:
            break
    if in_network and out_network:
        return True
    return False


#identify EC2 instances that have failed health checks more than 100 times in a single day
def health_check(instance_id):
    # Get current time and 15 days ago time
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=15)
    failed_checks_count = {}
    # Loop over each day in the last 15 days
    for day in range(15):
        current_day_start = start_time + timedelta(days=day)
        current_day_end = current_day_start + timedelta(days=1)
        metric_data = cloudwatch.get_metric_data(
            MetricDataQueries=[
                {
                    'Id': 'failedChecks',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/EC2',
                            'MetricName': 'StatusCheckFailed',
                            'Dimensions': [
                                {
                                    'Name': 'InstanceId',
                                    'Value': instance_id 
                                },
                            ]
                        },
                        'Period': 86400,  # Daily
                        'Stat': 'Sum',  # Get the sum of status check failures for the day
                        'Unit': 'Count'
                    },
                    'ReturnData': True,
                },
            ],
            StartTime=current_day_start,
            EndTime=current_day_end,
        )

        # Process the metric_data to track failures
        for result in metric_data['MetricDataResults']:
            for i, value in enumerate(result['Values']):
                timestamp = result['Timestamps'][i].date()
                failed_checks_count[timestamp]= int(value)
    # Check for instances that have more than 100 failed health checks in any single day
    print('failed_health check: ', failed_checks_count)
    for day, counts in failed_checks_count.items():
            if counts > 100:
                #print(f"Instance {instance_id} has failed health checks {counts} times on a {day} in the last 15 days.")
                return True
    return False

#listing instnace which are stopped for last 15 days
def stopeed_instnaces(instnace_id, stopped_date, days=15):
    global stopped_instance
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    if stopped_date <= cutoff_date:
        stopped_instance.append(instnace_id)
        

def check_ec2():
    previous_generation_instance_id = []
    low_cpu_instances = []
    low_network_instances = []
    instnace_details = ec2.describe_instances()
    t_windows_instances = []
    dedicated_Tenancy_instnace = []
    low_network_3hrs = []
    not_AMD_instances = {}
    without_Graviton_instance= {}
    failed_health_check_instances = []
    graviton_instnace_type = ('c7g','m7g','t4g', 'r7g')
    count = 0
    for reservation in instnace_details['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            instance_type = instance['InstanceType']
            platform = instance['PlatformDetails']
            Tenancy = instance['Placement']['Tenancy']
            #print('Tenancy is : ',Tenancy)
            #for stopped instnaces
            instance_state = instance['State']['Name']
            if instance_state == 'stopped':
                state_transition_time = instance.get('StateTransitionReason', '')
                if "User initiated" in state_transition_time:
                    # Extract date from StateTransitionReason
                    stopped_date_str = state_transition_time.split('(')[-1].split(')')[0]
                    stopped_date = datetime.strptime(stopped_date_str, "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
                    stopeed_instnaces(instance_id, stopped_date)                   
            if instance_state == 'stopped' or instance_state == 'running':
                print(platform)
                #checking for previous generation or not
                if instance_type in previous_generation_instance_types:
                    previous_generation_instance_id.append(instance_id)
                #checking for standalone or not
                if standalone_instnace(instance_id):
                    print(f"{instance_id} is standalone")
                    #check for cpu utilization
                    cpu_metric_values = metrics_check(instance_id, 'CPUUtilization', 'Average', 'Percent', 86400, True, 'AWS/EC2', 'InstanceId')
                    if cpu_utilization(instance_id, 5.0, cpu_metric_values):
                        low_cpu_instances.append(instance_id)
                    if network_utilization(instance_id):
                        low_network_instances.append(instance_id)
                    if not instance_type.startswith('t'):
                        if platform == 'windows' and ec2.describe_instance_types(InstanceTypes=[instance_type])['InstanceTypes'][0]['VCpuInfo']['DefaultVCpus'] <= 8 :
                            t_windows_instances.append(instance_id)
                    if Tenancy == 'dedicated':
                        dedicated_Tenancy_instnace.append(instance_id)
                    if not instance_type.startswith(graviton_instnace_type):
                        without_Graviton_instance[instance_id]=instance_type
                    if network_usage(instance_id):
                        low_network_3hrs.append(instance_id)
                    if not instance_type.startswith(graviton_instnace_type) and not 'a' in instance_type:
                        not_AMD_instances[instance_id]=instance_type
                    if health_check(instance_id):
                        failed_health_check_instances.append(instance_id)
                count +=1
    print("************************final EC2 output is ******************************")
    print("previous Genration instnaces are: ", previous_generation_instance_id)
    print("instnace with AVG cpu utlisation less than 5 for last 15 days: ", low_cpu_instances)
    print("instnace with max network in and out less than 100 KB for last 15 days: ", low_network_instances)
    print("Instances running Windows OS with base reqirement of 8vCPU or less, hosted other than T instance family ", t_windows_instances)
    print("Instances with dedicated Tenancy are: ", dedicated_Tenancy_instnace)
    print("Instnaces which are running without Graviton Processor: ", without_Graviton_instance)
    print('low network in/out for consistently 3hrs in day instances are: ',low_network_3hrs)
    print('instances without AMD processor :', not_AMD_instances)
    print('failed health checks 100 times on a single day in the last 15 days: ', failed_health_check_instances)
    print('instnace stopped from last 15 days are:', stopped_instance)
    print('totla instance we have:', count)

#check_ec2()
