import boto3
#import os
import numpy as np
from datetime import datetime, timedelta, timezone

cloudwatch = boto3.client('cloudwatch')

def metrics_check(instance_id, metric_name, statistics, unit, period, daily, namespace, dim_name):
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=15)
    metrics = cloudwatch.get_metric_statistics(
        Period=period,  # data points interval
        StartTime=start_time,
        EndTime=end_time,
        MetricName=metric_name,
        Namespace=namespace,
        Statistics=[statistics],
        Dimensions=[{'Name': dim_name, 'Value': instance_id}],
        Unit = unit
    )
    if daily:
        return [datapoint[statistics] for datapoint in metrics['Datapoints']]
    else:
        return metrics['Datapoints']
    

def cpu_utilization(instance_id, threshold, cpu_metric_values):
    P99_THRESHOLD = threshold
    if cpu_metric_values:
        # Calculate P99 CPU utilization
        p99_value = np.percentile(cpu_metric_values, 99) 
        print(f'p99 value for {instance_id}: ',p99_value)
        # Check for the threshold
        if p99_value < P99_THRESHOLD:
            return True
        else:
            return False

