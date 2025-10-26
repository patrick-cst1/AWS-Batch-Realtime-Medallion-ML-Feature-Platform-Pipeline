"""
Backfill Features Job
Author: Patrick Cheung

Reprocess historical data to regenerate features for a specific time range.
Supports feature versioning and incremental backfilling.
"""

import sys
import argparse
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, from_unixtime, unix_timestamp, window,
    count, sum as spark_sum, avg, countDistinct, 
    row_number, coalesce
)
from pyspark.sql.window import Window
import boto3


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill features for historical data")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--bronze-prefix", required=True, help="Bronze prefix")
    parser.add_argument("--silver-prefix", required=True, help="Silver prefix")
    parser.add_argument("--gold-prefix", required=True, help="Gold prefix")
    parser.add_argument("--feature-group", required=True, help="Feature Group name")
    parser.add_argument("--start-date", required=True, help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Backfill end date (YYYY-MM-DD)")
    parser.add_argument("--feature-version", default="v1", help="Feature version to backfill")
    parser.add_argument("--chunk-size-days", type=int, default=1, help="Process in chunks of N days")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing data")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without writing data")
    return parser.parse_args()


def create_spark_session():
    return SparkSession.builder \
        .appName("BackfillFeatures") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", 
                "com.amazonaws.auth.DefaultAWSCredentialsProviderChain") \
        .getOrCreate()


def generate_date_chunks(start_date, end_date, chunk_size_days):
    """
    Generate date chunks for incremental processing
    """
    chunks = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    while current <= end:
        chunk_end = min(current + timedelta(days=chunk_size_days - 1), end)
        chunks.append({
            "start": current.strftime("%Y-%m-%d"),
            "end": chunk_end.strftime("%Y-%m-%d")
        })
        current = chunk_end + timedelta(days=1)
    
    return chunks


def process_bronze_to_silver(spark, bronze_path, silver_path, start_date, end_date, overwrite):
    """
    Backfill Bronze to Silver layer
    """
    print(f"Processing Bronze to Silver: {start_date} to {end_date}")
    
    # Read Bronze data from date range
    try:
        bronze_df = spark.read.json(f"{bronze_path}/*.json.gz")
        
        # Filter by date range
        filtered_df = bronze_df.filter(
            (col("ts") >= unix_timestamp(lit(f"{start_date}T00:00:00Z"))) &
            (col("ts") <= unix_timestamp(lit(f"{end_date}T23:59:59Z")))
        )
        
        # Data cleaning and validation
        silver_df = filtered_df \
            .filter(col("event_id").isNotNull()) \
            .filter(col("card_id").isNotNull()) \
            .filter(col("amount") > 0) \
            .dropDuplicates(["event_id"]) \
            .withColumn("processed_at", lit(datetime.utcnow().isoformat())) \
            .withColumn("backfill_flag", lit(True))
        
        record_count = silver_df.count()
        print(f"Cleaned records: {record_count}")
        
        if record_count == 0:
            print("Warning: No records found for this date range")
            return None
        
        # Generate date partitions
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current <= end_dt:
            dt_str = current.strftime("%Y-%m-%d")
            silver_output = f"{silver_path}/card_transactions/dt={dt_str}"
            
            # Filter data for this date
            daily_df = silver_df.filter(
                (col("ts") >= unix_timestamp(lit(f"{dt_str}T00:00:00Z"))) &
                (col("ts") < unix_timestamp(lit(f"{(current + timedelta(days=1)).strftime('%Y-%m-%d')}T00:00:00Z")))
            )
            
            if daily_df.count() > 0:
                mode = "overwrite" if overwrite else "append"
                print(f"Writing Silver data to {silver_output} (mode: {mode})")
                daily_df.write.mode(mode).parquet(silver_output)
            
            current += timedelta(days=1)
        
        return silver_df
        
    except Exception as e:
        print(f"Error processing Bronze to Silver: {e}")
        raise


def process_silver_to_gold(spark, silver_path, gold_path, start_date, end_date, feature_version, overwrite):
    """
    Backfill feature engineering from Silver to Gold
    """
    print(f"Processing Silver to Gold: {start_date} to {end_date}, version: {feature_version}")
    
    try:
        # Read Silver data with lookback window (need historical context for time-based features)
        lookback_days = 7  # For 7-day features
        lookback_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        
        silver_df = spark.read.parquet(f"{silver_path}/card_transactions")
        
        # Filter with lookback window
        feature_df = silver_df.filter(
            col("ts") >= unix_timestamp(lit(f"{lookback_start}T00:00:00Z"))
        ).withColumn("event_datetime", from_unixtime(col("ts")))
        
        # Window specs for aggregations
        window_1h = Window.partitionBy("card_id").orderBy("ts").rangeBetween(-3600, 0)
        window_24h = Window.partitionBy("card_id").orderBy("ts").rangeBetween(-86400, 0)
        window_7d = Window.partitionBy("card_id").orderBy("ts").rangeBetween(-604800, 0)
        
        # Feature engineering (version-specific logic can be added here)
        gold_df = feature_df \
            .withColumn("txn_count_1h", count("*").over(window_1h)) \
            .withColumn("txn_amount_1h", spark_sum("amount").over(window_1h)) \
            .withColumn("merchant_count_24h", countDistinct("merchant_id").over(window_24h)) \
            .withColumn("avg_amount_7d", avg("amount").over(window_7d)) \
            .withColumn("event_time", col("ts").cast("double")) \
            .withColumn("feature_version", lit(feature_version)) \
            .withColumn("backfill_timestamp", lit(datetime.utcnow().isoformat()))
        
        # Select final features
        gold_features = gold_df.select(
            "card_id",
            "event_id",
            "merchant_id",
            "amount",
            "currency",
            "country",
            "pos_mode",
            "event_time",
            "txn_count_1h",
            "txn_amount_1h",
            "merchant_count_24h",
            "avg_amount_7d",
            "feature_version",
            "backfill_timestamp"
        )
        
        # Filter to target date range only
        gold_features = gold_features.filter(
            (col("event_time") >= unix_timestamp(lit(f"{start_date}T00:00:00Z"))) &
            (col("event_time") <= unix_timestamp(lit(f"{end_date}T23:59:59Z")))
        )
        
        # Write to Gold by date
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current <= end_dt:
            dt_str = current.strftime("%Y-%m-%d")
            gold_output = f"{gold_path}/card_features/dt={dt_str}"
            
            # Filter data for this date
            daily_df = gold_features.filter(
                (col("event_time") >= unix_timestamp(lit(f"{dt_str}T00:00:00Z"))) &
                (col("event_time") < unix_timestamp(lit(f"{(current + timedelta(days=1)).strftime('%Y-%m-%d')}T00:00:00Z")))
            )
            
            if daily_df.count() > 0:
                mode = "overwrite" if overwrite else "append"
                print(f"Writing Gold data to {gold_output} (mode: {mode}, records: {daily_df.count()})")
                daily_df.write.mode(mode).parquet(gold_output)
            
            current += timedelta(days=1)
        
        return gold_features
        
    except Exception as e:
        print(f"Error processing Silver to Gold: {e}")
        raise


def upsert_to_feature_store(gold_df, feature_group_name, dry_run=False):
    """
    Upsert backfilled features to SageMaker Feature Store
    """
    if dry_run:
        print(f"[DRY RUN] Would upsert {gold_df.count()} records to Feature Store: {feature_group_name}")
        return
    
    print(f"Upserting backfilled features to Feature Store: {feature_group_name}")
    
    # Convert to Pandas for batch upsert
    features_pd = gold_df.toPandas()
    
    # Prepare records
    records = []
    for _, row in features_pd.iterrows():
        record = [
            {"FeatureName": "card_id", "ValueAsString": str(row["card_id"])},
            {"FeatureName": "event_id", "ValueAsString": str(row["event_id"])},
            {"FeatureName": "merchant_id", "ValueAsString": str(row["merchant_id"])},
            {"FeatureName": "amount", "ValueAsString": str(row["amount"])},
            {"FeatureName": "currency", "ValueAsString": str(row["currency"])},
            {"FeatureName": "country", "ValueAsString": str(row["country"])},
            {"FeatureName": "pos_mode", "ValueAsString": str(row["pos_mode"])},
            {"FeatureName": "event_time", "ValueAsString": str(row["event_time"])},
            {"FeatureName": "txn_count_1h", "ValueAsString": str(int(row["txn_count_1h"]))},
            {"FeatureName": "txn_amount_1h", "ValueAsString": str(row["txn_amount_1h"])},
            {"FeatureName": "merchant_count_24h", "ValueAsString": str(int(row["merchant_count_24h"]))},
            {"FeatureName": "avg_amount_7d", "ValueAsString": str(row["avg_amount_7d"])}
        ]
        records.append(record)
    
    # Batch upsert to Feature Store
    client = boto3.client("sagemaker-featurestore-runtime")
    
    batch_size = 100
    success_count = 0
    error_count = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        try:
            response = client.batch_put_record(
                FeatureGroupName=feature_group_name,
                Records=[{"Record": r} for r in batch]
            )
            
            if "Errors" in response and response["Errors"]:
                error_count += len(response["Errors"])
                print(f"Batch {i//batch_size + 1}: {len(response['Errors'])} errors")
            else:
                success_count += len(batch)
                print(f"Batch {i//batch_size + 1}: Upserted {len(batch)} records")
                
        except Exception as e:
            print(f"Error upserting batch {i//batch_size + 1}: {e}")
            error_count += len(batch)
    
    print(f"Upsert complete: {success_count} success, {error_count} errors")


def main():
    args = parse_args()
    
    print("=" * 80)
    print("BACKFILL JOB STARTED")
    print("=" * 80)
    print(f"Date range: {args.start_date} to {args.end_date}")
    print(f"Feature version: {args.feature_version}")
    print(f"Chunk size: {args.chunk_size_days} days")
    print(f"Overwrite mode: {args.overwrite}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 80)
    
    # Paths
    bronze_path = f"s3://{args.bucket}/{args.bronze_prefix}/card_authorization"
    silver_path = f"s3://{args.bucket}/{args.silver_prefix}"
    gold_path = f"s3://{args.bucket}/{args.gold_prefix}"
    
    # Create Spark session
    spark = create_spark_session()
    
    try:
        # Generate date chunks
        chunks = generate_date_chunks(args.start_date, args.end_date, args.chunk_size_days)
        print(f"Processing {len(chunks)} chunks")
        
        total_records_processed = 0
        
        for idx, chunk in enumerate(chunks, 1):
            print(f"\n{'=' * 80}")
            print(f"CHUNK {idx}/{len(chunks)}: {chunk['start']} to {chunk['end']}")
            print(f"{'=' * 80}")
            
            if not args.dry_run:
                # Process Bronze to Silver
                silver_df = process_bronze_to_silver(
                    spark, bronze_path, silver_path, 
                    chunk['start'], chunk['end'], 
                    args.overwrite
                )
                
                if silver_df is None or silver_df.count() == 0:
                    print(f"Skipping chunk {idx}: No data found")
                    continue
                
                # Process Silver to Gold
                gold_df = process_silver_to_gold(
                    spark, silver_path, gold_path,
                    chunk['start'], chunk['end'],
                    args.feature_version,
                    args.overwrite
                )
                
                chunk_records = gold_df.count()
                total_records_processed += chunk_records
                print(f"Chunk {idx} processed: {chunk_records} records")
                
                # Upsert to Feature Store
                upsert_to_feature_store(gold_df, args.feature_group, args.dry_run)
            else:
                print(f"[DRY RUN] Would process chunk {idx}")
        
        print("\n" + "=" * 80)
        print("BACKFILL JOB COMPLETED")
        print("=" * 80)
        print(f"Total records processed: {total_records_processed}")
        print(f"Date range: {args.start_date} to {args.end_date}")
        print(f"Feature version: {args.feature_version}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n{'!' * 80}")
        print(f"BACKFILL JOB FAILED")
        print(f"{'!' * 80}")
        print(f"Error: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
