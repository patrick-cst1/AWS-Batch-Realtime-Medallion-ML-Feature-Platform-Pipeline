"""
Setup SageMaker Model Monitor for Data Drift Detection
Author: Patrick Cheung

Simple Model Monitor setup for demo.
"""

import boto3
import sagemaker
from sagemaker.model_monitor import (
    DataCaptureConfig,
    DefaultModelMonitor,
    CronExpressionGenerator
)
from sagemaker.s3 import S3Uploader
import json
import pandas as pd


def enable_data_capture(endpoint_name, bucket, region='ap-southeast-1'):
    """
    Enable data capture on existing endpoint
    
    Note: Data capture must be enabled during deployment.
    This function shows how to update endpoint config.
    """
    print("=" * 80)
    print("ENABLING DATA CAPTURE")
    print("=" * 80)
    
    sagemaker_client = boto3.client('sagemaker', region_name=region)
    
    # Get current endpoint config
    endpoint = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
    current_config_name = endpoint['EndpointConfigName']
    
    print(f"\nEndpoint: {endpoint_name}")
    print(f"Current Config: {current_config_name}")
    
    # Create new endpoint config with data capture
    new_config_name = f"{endpoint_name}-with-capture-{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
    
    # Get current config details
    current_config = sagemaker_client.describe_endpoint_config(
        EndpointConfigName=current_config_name
    )
    
    capture_config = {
        'EnableCapture': True,
        'InitialSamplingPercentage': 100,  # Capture 100% for demo
        'DestinationS3Uri': f's3://{bucket}/model-monitor/data-capture',
        'CaptureOptions': [
            {'CaptureMode': 'Input'},
            {'CaptureMode': 'Output'}
        ]
    }
    
    print(f"\nData Capture Config:")
    print(f"  Sampling: 100%")
    print(f"  Destination: {capture_config['DestinationS3Uri']}")
    
    try:
        # Create new config
        sagemaker_client.create_endpoint_config(
            EndpointConfigName=new_config_name,
            ProductionVariants=current_config['ProductionVariants'],
            DataCaptureConfig=capture_config
        )
        
        # Update endpoint
        print(f"\nUpdating endpoint with new config...")
        sagemaker_client.update_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=new_config_name
        )
        
        print("✓ Data capture enabled")
        print("  Note: Endpoint update takes 5-10 minutes")
        
    except Exception as e:
        print(f"Warning: {e}")
        print("Note: Data capture should be enabled during initial deployment")


def create_baseline(
    endpoint_name,
    bucket,
    role_arn,
    baseline_data_path='models/artifacts/test_data.csv',
    region='ap-southeast-1'
):
    """
    Create baseline for Model Monitor
    """
    print("\n" + "=" * 80)
    print("CREATING BASELINE")
    print("=" * 80)
    
    session = sagemaker.Session(boto_session=boto3.Session(region_name=region))
    
    # Upload baseline data
    print("\n1. Uploading baseline data to S3...")
    baseline_s3_uri = S3Uploader.upload(
        baseline_data_path,
        f's3://{bucket}/model-monitor/baseline-data',
        sagemaker_session=session
    )
    print(f"   Baseline data: {baseline_s3_uri}")
    
    # Create monitor
    print("\n2. Creating Model Monitor...")
    monitor = DefaultModelMonitor(
        role=role_arn,
        instance_count=1,
        instance_type='ml.m5.xlarge',
        volume_size_in_gb=20,
        max_runtime_in_seconds=3600,
        sagemaker_session=session
    )
    
    # Suggest baseline
    print("\n3. Generating baseline statistics and constraints...")
    print("   This may take 5-10 minutes...")
    
    from sagemaker.model_monitor.dataset_format import DatasetFormat
    
    baseline_results = monitor.suggest_baseline(
        baseline_dataset=baseline_s3_uri,
        dataset_format=DatasetFormat.csv(header=True),
        output_s3_uri=f's3://{bucket}/model-monitor/baseline-results',
        wait=True,
        logs=False
    )
    
    print("\n✓ Baseline created")
    print(f"   Statistics: {baseline_results.statistics}")
    print(f"   Constraints: {baseline_results.constraints}")
    
    return monitor, baseline_results


def create_monitoring_schedule(
    monitor,
    endpoint_name,
    bucket,
    baseline_results,
    schedule_name=None,
    region='ap-southeast-1'
):
    """
    Create monitoring schedule to detect drift
    """
    print("\n" + "=" * 80)
    print("CREATING MONITORING SCHEDULE")
    print("=" * 80)
    
    if schedule_name is None:
        schedule_name = f"{endpoint_name}-monitor"
    
    print(f"\nSchedule Name: {schedule_name}")
    print(f"Frequency: Hourly")
    print(f"Data Capture: s3://{bucket}/model-monitor/data-capture")
    print(f"Reports: s3://{bucket}/model-monitor/reports")
    
    try:
        monitor.create_monitoring_schedule(
            monitor_schedule_name=schedule_name,
            endpoint_input=endpoint_name,
            output_s3_uri=f's3://{bucket}/model-monitor/reports',
            statistics=baseline_results.statistics,
            constraints=baseline_results.constraints,
            schedule_cron_expression=CronExpressionGenerator.hourly(),  # Run hourly
            enable_cloudwatch_metrics=True
        )
        
        print("\n✓ Monitoring schedule created")
        print("\nCloudWatch Metrics:")
        print("  Namespace: aws/sagemaker/Endpoints/data-metrics")
        print(f"  Dimension: Endpoint={endpoint_name}")
        
        print("\nDrift Detection:")
        print("  - Feature drift (distribution changes)")
        print("  - Data quality issues")
        print("  - Schema violations")
        
    except Exception as e:
        if 'already exists' in str(e):
            print(f"\n✓ Schedule already exists: {schedule_name}")
        else:
            raise


def setup_drift_alerts(endpoint_name, region='ap-southeast-1'):
    """
    Setup CloudWatch alarms for drift detection
    """
    print("\n" + "=" * 80)
    print("SETTING UP DRIFT ALERTS")
    print("=" * 80)
    
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    
    alarm_name = f"{endpoint_name}-drift-detected"
    
    print(f"\nAlarm Name: {alarm_name}")
    
    try:
        cloudwatch.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=1,
            MetricName='feature_baseline_drift_txn_count_1h',
            Namespace='aws/sagemaker/Endpoints/data-metrics',
            Period=3600,
            Statistic='Average',
            Threshold=0.1,  # 10% drift threshold
            ActionsEnabled=False,  # Enable this when you have SNS topic
            AlarmDescription='Alert when data drift detected',
            Dimensions=[
                {
                    'Name': 'Endpoint',
                    'Value': endpoint_name
                }
            ]
        )
        
        print("✓ Drift alarm created")
        print(f"  Threshold: 10% drift")
        print(f"  To enable SNS notifications, add SNS topic ARN")
        
    except Exception as e:
        if 'already exists' in str(e):
            print(f"✓ Alarm already exists: {alarm_name}")
        else:
            print(f"Warning: Could not create alarm: {e}")


def main():
    """
    Main setup workflow
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup Model Monitor")
    parser.add_argument('--endpoint-name', required=True, help='SageMaker endpoint name')
    parser.add_argument('--bucket', required=True, help='S3 bucket for monitoring data')
    parser.add_argument('--role-arn', required=True, help='SageMaker execution role ARN')
    parser.add_argument('--region', default='ap-southeast-1', help='AWS region')
    parser.add_argument('--skip-data-capture', action='store_true', 
                        help='Skip data capture setup (should be done during deployment)')
    
    args = parser.parse_args()
    
    # Step 1: Enable data capture (if not already)
    if not args.skip_data_capture:
        enable_data_capture(args.endpoint_name, args.bucket, args.region)
        print("\n⚠️  Wait for endpoint update to complete before creating baseline")
        print("   Check status: aws sagemaker describe-endpoint --endpoint-name", args.endpoint_name)
        return
    
    # Step 2: Create baseline
    monitor, baseline_results = create_baseline(
        endpoint_name=args.endpoint_name,
        bucket=args.bucket,
        role_arn=args.role_arn,
        region=args.region
    )
    
    # Step 3: Create monitoring schedule
    create_monitoring_schedule(
        monitor=monitor,
        endpoint_name=args.endpoint_name,
        bucket=args.bucket,
        baseline_results=baseline_results,
        region=args.region
    )
    
    # Step 4: Setup CloudWatch alerts
    setup_drift_alerts(args.endpoint_name, args.region)
    
    # Save configuration
    config = {
        'endpoint_name': args.endpoint_name,
        'monitor_schedule': f"{args.endpoint_name}-monitor",
        'baseline_uri': f"s3://{args.bucket}/model-monitor/baseline-results",
        'data_capture_uri': f"s3://{args.bucket}/model-monitor/data-capture",
        'reports_uri': f"s3://{args.bucket}/model-monitor/reports"
    }
    
    with open('models/monitor_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\n" + "=" * 80)
    print("✓ MODEL MONITOR SETUP COMPLETED")
    print("=" * 80)
    print("\nConfiguration saved to: models/monitor_config.json")
    print("\nNext Steps:")
    print("1. Send some predictions to the endpoint")
    print("2. Wait for hourly monitoring job to run")
    print("3. Check drift reports in S3 or CloudWatch")


if __name__ == "__main__":
    main()
