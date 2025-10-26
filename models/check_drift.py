"""
Check Data Drift from Model Monitor
Author: Patrick Cheung

Simple script to check drift detection results.
"""

import boto3
import json
from datetime import datetime, timedelta
import pandas as pd


def check_monitoring_schedule(endpoint_name, region='ap-southeast-1'):
    """
    Check monitoring schedule status
    """
    print("=" * 80)
    print("MONITORING SCHEDULE STATUS")
    print("=" * 80)
    
    sagemaker = boto3.client('sagemaker', region_name=region)
    
    schedule_name = f"{endpoint_name}-monitor"
    
    try:
        response = sagemaker.describe_monitoring_schedule(
            MonitoringScheduleName=schedule_name
        )
        
        print(f"\nSchedule Name: {schedule_name}")
        print(f"Status: {response['MonitoringScheduleStatus']}")
        print(f"Created: {response['CreationTime']}")
        
        if 'LastMonitoringExecutionSummary' in response:
            last_run = response['LastMonitoringExecutionSummary']
            print(f"\nLast Execution:")
            print(f"  Status: {last_run['MonitoringExecutionStatus']}")
            print(f"  Started: {last_run['ScheduledTime']}")
            if 'EndTime' in last_run:
                print(f"  Ended: {last_run['EndTime']}")
            
            if 'ProcessingJobArn' in last_run:
                job_name = last_run['ProcessingJobArn'].split('/')[-1]
                print(f"  Job: {job_name}")
        else:
            print("\nNo executions yet. Wait for first scheduled run.")
        
        return response
        
    except sagemaker.exceptions.ResourceNotFound:
        print(f"\n✗ Monitoring schedule not found: {schedule_name}")
        return None


def list_drift_reports(bucket, endpoint_name, max_reports=5):
    """
    List recent drift reports from S3
    """
    print("\n" + "=" * 80)
    print("RECENT DRIFT REPORTS")
    print("=" * 80)
    
    s3 = boto3.client('s3')
    
    prefix = f"model-monitor/reports/{endpoint_name}"
    
    try:
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=100
        )
        
        if 'Contents' not in response:
            print(f"\nNo reports found in s3://{bucket}/{prefix}")
            print("Note: Reports are generated after monitoring jobs complete")
            return []
        
        # Filter for constraint violations files
        violations_files = [
            obj for obj in response['Contents']
            if 'constraint_violations.json' in obj['Key']
        ]
        
        violations_files.sort(key=lambda x: x['LastModified'], reverse=True)
        
        print(f"\nFound {len(violations_files)} reports")
        print(f"Showing latest {min(max_reports, len(violations_files))}:\n")
        
        reports = []
        for obj in violations_files[:max_reports]:
            print(f"  {obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')} - {obj['Key']}")
            reports.append(obj['Key'])
        
        return reports
        
    except Exception as e:
        print(f"\n✗ Error listing reports: {e}")
        return []


def analyze_drift_report(bucket, report_key):
    """
    Analyze a specific drift report
    """
    print("\n" + "=" * 80)
    print("DRIFT ANALYSIS")
    print("=" * 80)
    
    s3 = boto3.client('s3')
    
    try:
        # Download violations report
        print(f"\nAnalyzing: {report_key}")
        
        response = s3.get_object(Bucket=bucket, Key=report_key)
        violations = json.loads(response['Body'].read().decode())
        
        if 'violations' not in violations or len(violations['violations']) == 0:
            print("\n✓ No drift detected!")
            print("  All features are within baseline constraints")
            return
        
        print(f"\n⚠️  DRIFT DETECTED: {len(violations['violations'])} violations")
        print("-" * 80)
        
        for i, violation in enumerate(violations['violations'], 1):
            print(f"\nViolation {i}:")
            print(f"  Feature: {violation.get('feature_name', 'N/A')}")
            print(f"  Constraint: {violation.get('constraint_check_type', 'N/A')}")
            print(f"  Description: {violation.get('description', 'N/A')}")
            
        # Download statistics for comparison
        stats_key = report_key.replace('constraint_violations.json', 'statistics.json')
        try:
            response = s3.get_object(Bucket=bucket, Key=stats_key)
            stats = json.loads(response['Body'].read().decode())
            
            print("\n" + "-" * 80)
            print("FEATURE STATISTICS:")
            
            if 'features' in stats:
                for feature in stats['features'][:5]:  # Show first 5
                    print(f"\n  {feature.get('name', 'Unknown')}:")
                    if 'number_statistics' in feature:
                        num_stats = feature['number_statistics']
                        print(f"    Mean: {num_stats.get('common', {}).get('mean', 'N/A')}")
                        print(f"    Std: {num_stats.get('common', {}).get('std_dev', 'N/A')}")
                        print(f"    Min: {num_stats.get('common', {}).get('min', 'N/A')}")
                        print(f"    Max: {num_stats.get('common', {}).get('max', 'N/A')}")
        except:
            pass
        
    except Exception as e:
        print(f"\n✗ Error analyzing report: {e}")


def check_cloudwatch_metrics(endpoint_name, region='ap-southeast-1'):
    """
    Check CloudWatch metrics for drift
    """
    print("\n" + "=" * 80)
    print("CLOUDWATCH METRICS")
    print("=" * 80)
    
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)
    
    print(f"\nTime Range: Last 24 hours")
    print(f"Endpoint: {endpoint_name}")
    
    # Query feature drift metrics
    try:
        response = cloudwatch.get_metric_statistics(
            Namespace='aws/sagemaker/Endpoints/data-metrics',
            MetricName='feature_baseline_drift',
            Dimensions=[
                {'Name': 'Endpoint', 'Value': endpoint_name}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average', 'Maximum']
        )
        
        if response['Datapoints']:
            print("\nFeature Drift Metrics:")
            for dp in sorted(response['Datapoints'], key=lambda x: x['Timestamp']):
                print(f"  {dp['Timestamp'].strftime('%Y-%m-%d %H:%M')} - "
                      f"Avg: {dp.get('Average', 0):.4f}, "
                      f"Max: {dp.get('Maximum', 0):.4f}")
        else:
            print("\nNo drift metrics available yet")
            print("Note: Metrics appear after monitoring jobs run")
        
    except Exception as e:
        print(f"\n✗ Error fetching metrics: {e}")


def main():
    """
    Main drift checking workflow
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Check data drift")
    parser.add_argument('--endpoint-name', required=True, help='SageMaker endpoint name')
    parser.add_argument('--bucket', required=True, help='S3 bucket with reports')
    parser.add_argument('--region', default='ap-southeast-1', help='AWS region')
    parser.add_argument('--max-reports', type=int, default=5, help='Max reports to show')
    
    args = parser.parse_args()
    
    # Check monitoring schedule
    schedule_status = check_monitoring_schedule(args.endpoint_name, args.region)
    
    # List drift reports
    reports = list_drift_reports(args.bucket, args.endpoint_name, args.max_reports)
    
    # Analyze latest report if available
    if reports:
        print("\n" + "=" * 80)
        choice = input("\nAnalyze latest report? (y/n): ")
        if choice.lower() == 'y':
            analyze_drift_report(args.bucket, reports[0])
    
    # Check CloudWatch metrics
    check_cloudwatch_metrics(args.endpoint_name, args.region)
    
    print("\n" + "=" * 80)
    print("✓ DRIFT CHECK COMPLETED")
    print("=" * 80)
    
    print("\nUseful Commands:")
    print(f"  # View reports in S3")
    print(f"  aws s3 ls s3://{args.bucket}/model-monitor/reports/{args.endpoint_name}/ --recursive")
    print(f"\n  # Describe monitoring schedule")
    print(f"  aws sagemaker describe-monitoring-schedule --monitoring-schedule-name {args.endpoint_name}-monitor")


if __name__ == "__main__":
    main()
