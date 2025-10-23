"""
Silver and Gold Layer Processing Job
Author: Patrick Cheung

Reads Bronze streaming data, cleans it (Silver), 
performs feature engineering (Gold), and upserts to SageMaker Feature Store.
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
    parser = argparse.ArgumentParser(description="Silver and Gold layer processing")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--bronze-prefix", required=True, help="Bronze prefix")
    parser.add_argument("--silver-prefix", required=True, help="Silver prefix")
    parser.add_argument("--gold-prefix", required=True, help="Gold prefix")
    parser.add_argument("--feature-group", required=True, help="Feature Group name")
    parser.add_argument("--window-end-ts", required=True, help="Window end timestamp")
    parser.add_argument("--lookback-minutes", type=int, default=60, help="Lookback minutes")
    parser.add_argument("--watermark-delay-minutes", type=int, default=2, help="Watermark delay")
    parser.add_argument("--feature-version", default="v1", help="Feature version")
    return parser.parse_args()


def create_spark_session():
    return SparkSession.builder \
        .appName("SilverGoldProcessing") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", 
                "com.amazonaws.auth.DefaultAWSCredentialsProviderChain") \
        .getOrCreate()


def process_bronze_to_silver(spark, bronze_path, silver_path, window_start, window_end):
    """
    Read Bronze data and clean to Silver layer
    """
    print(f"Reading Bronze data from {bronze_path}")
    print(f"Window: {window_start} to {window_end}")
    
    # Read Bronze data
    bronze_df = spark.read.json(f"{bronze_path}/*.json.gz")
    
    # Filter by window
    filtered_df = bronze_df.filter(
        (col("ts") >= unix_timestamp(lit(window_start))) &
        (col("ts") <= unix_timestamp(lit(window_end)))
    )
    
    # Data cleaning and validation
    silver_df = filtered_df \
        .filter(col("event_id").isNotNull()) \
        .filter(col("card_id").isNotNull()) \
        .filter(col("amount") > 0) \
        .dropDuplicates(["event_id"]) \
        .withColumn("processed_at", lit(datetime.utcnow().isoformat()))
    
    # Write to Silver
    dt = window_end.split("T")[0]
    silver_output = f"{silver_path}/card_transactions/dt={dt}"
    
    print(f"Writing Silver data to {silver_output}")
    silver_df.write \
        .mode("append") \
        .partitionBy("dt") \
        .parquet(silver_output)
    
    return silver_df


def process_silver_to_gold(spark, silver_df, gold_path, window_end, feature_version="v1"):
    """
    Perform feature engineering from Silver to Gold
    """
    print(f"Processing Silver to Gold with feature engineering (version: {feature_version})")
    
    # Convert timestamp to datetime
    feature_df = silver_df.withColumn(
        "event_datetime", 
        from_unixtime(col("ts"))
    )
    
    # Window specs for aggregations
    window_1h = Window.partitionBy("card_id").orderBy("ts").rangeBetween(-3600, 0)
    window_24h = Window.partitionBy("card_id").orderBy("ts").rangeBetween(-86400, 0)
    window_7d = Window.partitionBy("card_id").orderBy("ts").rangeBetween(-604800, 0)
    
    # Feature engineering (version-specific logic can be customized here)
    gold_df = feature_df \
        .withColumn("txn_count_1h", count("*").over(window_1h)) \
        .withColumn("txn_amount_1h", spark_sum("amount").over(window_1h)) \
        .withColumn("merchant_count_24h", countDistinct("merchant_id").over(window_24h)) \
        .withColumn("avg_amount_7d", avg("amount").over(window_7d)) \
        .withColumn("event_time", col("ts").cast("double")) \
        .withColumn("feature_version", lit(feature_version)) \
        .withColumn("processing_timestamp", lit(datetime.utcnow().isoformat()))
    
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
        "processing_timestamp"
    )
    
    # Write to Gold
    dt = window_end.split("T")[0]
    gold_output = f"{gold_path}/card_features/dt={dt}"
    
    print(f"Writing Gold data to {gold_output}")
    gold_features.write \
        .mode("append") \
        .partitionBy("dt") \
        .parquet(gold_output)
    
    return gold_features


def upsert_to_feature_store(gold_df, feature_group_name):
    """
    Upsert features to SageMaker Feature Store
    """
    print(f"Upserting to Feature Store: {feature_group_name}")
    
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
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        try:
            response = client.batch_put_record(
                FeatureGroupName=feature_group_name,
                Records=[{"Record": r} for r in batch]
            )
            print(f"Batch {i//batch_size + 1}: Upserted {len(batch)} records")
        except Exception as e:
            print(f"Error upserting batch {i//batch_size + 1}: {e}")
            raise
    
    print(f"Total records upserted: {len(records)}")


def main():
    args = parse_args()
    
    # Calculate window
    window_end = datetime.fromisoformat(args.window_end_ts.replace("Z", "+00:00"))
    window_start = window_end - timedelta(minutes=args.lookback_minutes)
    
    # Paths
    bronze_path = f"s3://{args.bucket}/{args.bronze_prefix}/card_authorization"
    silver_path = f"s3://{args.bucket}/{args.silver_prefix}"
    gold_path = f"s3://{args.bucket}/{args.gold_prefix}"
    
    # Create Spark session
    spark = create_spark_session()
    
    try:
        # Process Bronze to Silver
        silver_df = process_bronze_to_silver(
            spark, bronze_path, silver_path, 
            window_start.isoformat(), window_end.isoformat()
        )
        
        # Process Silver to Gold
        gold_df = process_silver_to_gold(
            spark, silver_df, gold_path, window_end.isoformat(), args.feature_version
        )
        
        # Upsert to Feature Store
        upsert_to_feature_store(gold_df, args.feature_group)
        
        print("Silver and Gold processing completed successfully")
        
    except Exception as e:
        print(f"Error in processing: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
