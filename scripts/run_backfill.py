"""
Backfill Helper Script
Author: Patrick Cheung

Convenient wrapper to trigger backfill jobs via Step Functions or direct EMR execution.
"""

import argparse
import json
import boto3
from datetime import datetime, timedelta


def parse_args():
    parser = argparse.ArgumentParser(description="Trigger feature backfill job")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--feature-version", default="v1", help="Feature version (default: v1)")
    parser.add_argument("--chunk-size-days", type=int, default=1, help="Chunk size in days (default: 1)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing data")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without writing data")
    
    # AWS Configuration
    parser.add_argument("--state-machine-arn", help="Step Functions state machine ARN for backfill")
    parser.add_argument("--bucket", help="S3 datalake bucket name")
    parser.add_argument("--code-bucket", help="S3 code bucket name")
    parser.add_argument("--emr-app-id", help="EMR Serverless application ID")
    parser.add_argument("--emr-job-role", help="EMR job execution role ARN")
    parser.add_argument("--feature-group", default="rt_card_features_v1", help="Feature group name")
    parser.add_argument("--glue-crawler", help="Glue crawler name")
    parser.add_argument("--region", default="ap-southeast-1", help="AWS region")
    
    # Execution mode
    parser.add_argument("--direct-emr", action="store_true", help="Submit directly to EMR (skip Step Functions)")
    
    return parser.parse_args()


def validate_date_range(start_date, end_date):
    """Validate date range"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start > end:
            raise ValueError(f"Start date {start_date} is after end date {end_date}")
        
        if end > datetime.utcnow():
            raise ValueError(f"End date {end_date} is in the future")
        
        days_diff = (end - start).days
        if days_diff > 365:
            print(f"Warning: Large date range ({days_diff} days). Consider breaking into smaller chunks.")
        
        return True
    except ValueError as e:
        raise ValueError(f"Invalid date format or range: {e}")


def trigger_stepfunctions_backfill(args):
    """Trigger backfill via Step Functions"""
    print("=" * 80)
    print("TRIGGERING BACKFILL VIA STEP FUNCTIONS")
    print("=" * 80)
    
    client = boto3.client("stepfunctions", region_name=args.region)
    
    execution_input = {
        "bucket": args.bucket,
        "codeBucket": args.code_bucket,
        "startDate": args.start_date,
        "endDate": args.end_date,
        "featureVersion": args.feature_version,
        "chunkSizeDays": args.chunk_size_days,
        "overwrite": args.overwrite,
        "dryRun": args.dry_run,
        "featureGroup": args.feature_group,
        "emr": {
            "appId": args.emr_app_id,
            "jobRole": args.emr_job_role
        },
        "glue": {
            "crawlerName": args.glue_crawler
        }
    }
    
    execution_name = f"backfill-{args.start_date}-to-{args.end_date}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    
    print(f"State Machine: {args.state_machine_arn}")
    print(f"Execution Name: {execution_name}")
    print(f"Input:")
    print(json.dumps(execution_input, indent=2))
    print()
    
    response = client.start_execution(
        stateMachineArn=args.state_machine_arn,
        name=execution_name,
        input=json.dumps(execution_input)
    )
    
    execution_arn = response["executionArn"]
    print(f"✓ Backfill execution started successfully")
    print(f"Execution ARN: {execution_arn}")
    print()
    print(f"Monitor progress:")
    print(f"  AWS Console: https://{args.region}.console.aws.amazon.com/states/home?region={args.region}#/executions/details/{execution_arn}")
    print()
    
    return response


def trigger_direct_emr_backfill(args):
    """Trigger backfill directly via EMR Serverless"""
    print("=" * 80)
    print("TRIGGERING BACKFILL DIRECTLY VIA EMR SERVERLESS")
    print("=" * 80)
    
    client = boto3.client("emr-serverless", region_name=args.region)
    
    entry_point_args = [
        "--bucket", args.bucket,
        "--bronze-prefix", "bronze/streaming",
        "--silver-prefix", "silver",
        "--gold-prefix", "gold",
        "--feature-group", args.feature_group,
        "--start-date", args.start_date,
        "--end-date", args.end_date,
        "--feature-version", args.feature_version,
        "--chunk-size-days", str(args.chunk_size_days)
    ]
    
    if args.overwrite:
        entry_point_args.append("--overwrite")
    if args.dry_run:
        entry_point_args.append("--dry-run")
    
    job_name = f"backfill-{args.start_date}-to-{args.end_date}"
    
    print(f"EMR Application ID: {args.emr_app_id}")
    print(f"Job Name: {job_name}")
    print(f"Entry Point: s3://{args.code_bucket}/spark_jobs/backfill_features.py")
    print(f"Arguments: {' '.join(entry_point_args)}")
    print()
    
    response = client.start_job_run(
        applicationId=args.emr_app_id,
        executionRoleArn=args.emr_job_role,
        name=job_name,
        jobDriver={
            "sparkSubmit": {
                "entryPoint": f"s3://{args.code_bucket}/spark_jobs/backfill_features.py",
                "entryPointArguments": entry_point_args,
                "sparkSubmitParameters": (
                    "--conf spark.executor.cores=2 "
                    "--conf spark.executor.memory=8g "
                    "--conf spark.driver.cores=2 "
                    "--conf spark.driver.memory=8g "
                    "--conf spark.executor.instances=4"
                )
            }
        }
    )
    
    job_run_id = response["jobRunId"]
    print(f"✓ Backfill job submitted successfully")
    print(f"Job Run ID: {job_run_id}")
    print()
    print(f"Monitor progress:")
    print(f"  AWS Console: https://{args.region}.console.aws.amazon.com/emr/home?region={args.region}#/serverless/applications/{args.emr_app_id}/job-runs/{job_run_id}")
    print()
    print(f"Check logs:")
    print(f"  aws emr-serverless get-job-run --application-id {args.emr_app_id} --job-run-id {job_run_id}")
    print()
    
    return response


def estimate_backfill_cost(start_date, end_date, chunk_size_days):
    """Rough cost estimation for backfill"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days + 1
    
    # Rough estimates (adjust based on data volume)
    avg_job_duration_min = 10  # minutes per chunk
    num_chunks = (days + chunk_size_days - 1) // chunk_size_days
    total_duration_hours = (num_chunks * avg_job_duration_min) / 60
    
    # EMR Serverless pricing (ap-southeast-1, rough estimate)
    # Assume 4 executors × 2 vCPU × 8GB + 1 driver × 2 vCPU × 8GB = 10 vCPU, 40 GB
    vcpu_hours = 10 * total_duration_hours
    gb_hours = 40 * total_duration_hours
    
    vcpu_cost = vcpu_hours * 0.052624  # USD per vCPU-hour
    gb_cost = gb_hours * 0.0057785    # USD per GB-hour
    
    estimated_cost = vcpu_cost + gb_cost
    
    print("=" * 80)
    print("COST ESTIMATION (ROUGH)")
    print("=" * 80)
    print(f"Date range: {days} days")
    print(f"Chunks: {num_chunks} (chunk size: {chunk_size_days} days)")
    print(f"Estimated total duration: {total_duration_hours:.1f} hours")
    print(f"Estimated EMR Serverless cost: ${estimated_cost:.2f} USD")
    print()
    print("Note: This is a rough estimate. Actual cost depends on:")
    print("  - Data volume and complexity")
    print("  - Spark configuration and optimization")
    print("  - S3 read/write costs")
    print("  - Feature Store ingestion costs")
    print("=" * 80)
    print()


def main():
    args = parse_args()
    
    # Validate inputs
    print()
    validate_date_range(args.start_date, args.end_date)
    
    # Show cost estimation
    estimate_backfill_cost(args.start_date, args.end_date, args.chunk_size_days)
    
    # Confirmation prompt
    if not args.dry_run:
        print("⚠️  WARNING: This will process and potentially overwrite historical data.")
        confirmation = input("Do you want to proceed? (yes/no): ")
        if confirmation.lower() not in ["yes", "y"]:
            print("Backfill cancelled.")
            return
        print()
    
    # Trigger backfill
    try:
        if args.direct_emr:
            if not all([args.emr_app_id, args.emr_job_role, args.bucket, args.code_bucket]):
                raise ValueError("--direct-emr requires: --emr-app-id, --emr-job-role, --bucket, --code-bucket")
            trigger_direct_emr_backfill(args)
        else:
            if not args.state_machine_arn:
                raise ValueError("--state-machine-arn required (or use --direct-emr)")
            trigger_stepfunctions_backfill(args)
        
        print("=" * 80)
        print("✓ BACKFILL TRIGGERED SUCCESSFULLY")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Error triggering backfill: {e}")
        raise


if __name__ == "__main__":
    main()
