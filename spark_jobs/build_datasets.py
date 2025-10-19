"""
Build Training and Inference Datasets Job
Author: Patrick Cheung

Reads Gold layer data and builds training and inference datasets.
"""

import sys
import argparse
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, row_number, rand
from pyspark.sql.window import Window
import json


def parse_args():
    parser = argparse.ArgumentParser(description="Build training and inference datasets")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--gold-prefix", required=True, help="Gold prefix")
    parser.add_argument("--training-prefix", required=True, help="Training prefix")
    parser.add_argument("--inference-prefix", required=True, help="Inference prefix")
    parser.add_argument("--lookback-days", type=int, default=30, help="Lookback days for training")
    return parser.parse_args()


def create_spark_session():
    return SparkSession.builder \
        .appName("BuildDatasets") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", 
                "com.amazonaws.auth.DefaultAWSCredentialsProviderChain") \
        .getOrCreate()


def build_training_dataset(spark, gold_path, training_path, lookback_days):
    """
    Build training dataset from Gold layer
    """
    print(f"Building training dataset from {gold_path}")
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    # Read Gold data
    gold_df = spark.read.parquet(f"{gold_path}/card_features")
    
    # Filter by date range
    training_df = gold_df.filter(
        col("dt").between(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    )
    
    # Add label (simulated fraud detection label for demo)
    # In production, this would come from actual fraud labels
    training_with_label = training_df.withColumn(
        "is_fraud",
        (col("amount") > 1000).cast("int")  # Simple heuristic for demo
    )
    
    # Train/validation split (80/20)
    train_df, val_df = training_with_label.randomSplit([0.8, 0.2], seed=42)
    
    # Write training set
    train_output = f"{training_path}/dt={end_date.strftime('%Y-%m-%d')}/train"
    print(f"Writing training data to {train_output}")
    train_df.write.mode("overwrite").parquet(train_output)
    
    # Write validation set
    val_output = f"{training_path}/dt={end_date.strftime('%Y-%m-%d')}/validation"
    print(f"Writing validation data to {val_output}")
    val_df.write.mode("overwrite").parquet(val_output)
    
    # Save metadata
    metadata = {
        "created_at": datetime.utcnow().isoformat(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "train_count": train_df.count(),
        "val_count": val_df.count(),
        "feature_version": "v1"
    }
    
    return metadata


def build_inference_dataset(spark, gold_path, inference_path):
    """
    Build inference dataset from latest Gold data
    """
    print(f"Building inference dataset from {gold_path}")
    
    # Read latest Gold data
    gold_df = spark.read.parquet(f"{gold_path}/card_features")
    
    # Get latest data (last 24 hours)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    inference_df = gold_df.filter(
        col("dt").isin([today, yesterday])
    )
    
    # Select features only (no labels)
    inference_features = inference_df.select([
        c for c in inference_df.columns if c not in ["is_fraud", "dt"]
    ])
    
    # Write inference set
    inference_output = f"{inference_path}/dt={today}"
    print(f"Writing inference data to {inference_output}")
    inference_features.write.mode("overwrite").parquet(inference_output)
    
    # Save metadata
    metadata = {
        "created_at": datetime.utcnow().isoformat(),
        "date": today,
        "count": inference_features.count(),
        "feature_version": "v1"
    }
    
    return metadata


def save_metadata(spark, bucket, metadata, dataset_type):
    """
    Save dataset metadata to S3
    """
    metadata_path = f"s3://{bucket}/metadata/{dataset_type}_metadata.json"
    print(f"Saving metadata to {metadata_path}")
    
    # Convert to JSON and save
    metadata_json = json.dumps(metadata, indent=2)
    spark.sparkContext.parallelize([metadata_json]).coalesce(1).saveAsTextFile(
        metadata_path.replace(".json", "_tmp")
    )
    
    print(f"Metadata saved: {metadata}")


def main():
    args = parse_args()
    
    # Paths
    gold_path = f"s3://{args.bucket}/{args.gold_prefix}"
    training_path = f"s3://{args.bucket}/{args.training_prefix}"
    inference_path = f"s3://{args.bucket}/{args.inference_prefix}"
    
    # Create Spark session
    spark = create_spark_session()
    
    try:
        # Build training dataset
        train_metadata = build_training_dataset(
            spark, gold_path, training_path, args.lookback_days
        )
        save_metadata(spark, args.bucket, train_metadata, "training")
        
        # Build inference dataset
        inference_metadata = build_inference_dataset(
            spark, gold_path, inference_path
        )
        save_metadata(spark, args.bucket, inference_metadata, "inference")
        
        print("Dataset building completed successfully")
        
    except Exception as e:
        print(f"Error in dataset building: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
