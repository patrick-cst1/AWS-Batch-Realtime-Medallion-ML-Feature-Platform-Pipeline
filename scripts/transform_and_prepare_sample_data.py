#!/usr/bin/env python3
"""
Transform sample NDJSON transactions to Bronze Layer format locally.
Output: compressed JSON or Parquet files in desired directory structure.
Author: Patrick Cheung
"""

import json
import gzip
import os
from pathlib import Path
from datetime import datetime
import argparse
from typing import List, Dict, Any
import pandas as pd


def read_ndjson(file_path: str) -> List[Dict[str, Any]]:
    """Read NDJSON file and return list of records."""
    records = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def transform_records(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Transform records to desired schema with validation.
    
    Expected fields:
    - event_id, card_id, ts, merchant_id, amount, currency, country, pos_mode
    """
    df = pd.DataFrame(records)
    
    # Validate required columns
    required_cols = ['event_id', 'card_id', 'ts', 'merchant_id', 
                     'amount', 'currency', 'country', 'pos_mode']
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    
    # Convert timestamp to datetime
    df['ts'] = pd.to_datetime(df['ts'], unit='s')
    
    # Type conversions
    df['amount'] = df['amount'].astype(float)
    df = df[required_cols]  # Keep only required columns
    
    return df


def save_as_compressed_json(df: pd.DataFrame, output_file: str) -> None:
    """Save DataFrame as gzip-compressed NDJSON."""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with gzip.open(output_file, 'wt', encoding='utf-8') as f:
        for _, row in df.iterrows():
            json_line = json.dumps(row.to_dict(), default=str)
            f.write(json_line + '\n')
    
    print(f"✓ Saved compressed JSON: {output_file}")


def save_as_parquet(df: pd.DataFrame, output_file: str) -> None:
    """Save DataFrame as Parquet format."""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    df.to_parquet(output_file, index=False, compression='snappy')
    print(f"✓ Saved Parquet: {output_file}")


def create_bronze_directory_structure(df: pd.DataFrame, base_dir: str, format: str = 'json') -> str:
    """
    Create S3-like directory structure:
    bronze/streaming/card_authorization/ingest_dt=YYYY/MM/DD/HH/mm/
    
    Partitions by timestamp from first record for demo.
    """
    if df.empty:
        print("No records to process.")
        return ""
    
    # Use first record's timestamp for directory structure
    sample_ts = df.iloc[0]['ts']
    year = sample_ts.strftime('%Y')
    month = sample_ts.strftime('%m')
    day = sample_ts.strftime('%d')
    hour = sample_ts.strftime('%H')
    minute = sample_ts.strftime('%M')
    
    # Create partition path
    partition_path = os.path.join(
        base_dir,
        'bronze',
        'streaming',
        'card_authorization',
        f'ingest_dt={year}',
        month,
        day,
        hour,
        minute
    )
    
    if format.lower() == 'json':
        output_file = os.path.join(partition_path, 'data.json.gz')
        save_as_compressed_json(df, output_file)
    elif format.lower() == 'parquet':
        output_file = os.path.join(partition_path, 'data.parquet')
        save_as_parquet(df, output_file)
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    return partition_path


def main():
    parser = argparse.ArgumentParser(
        description='Transform sample transaction data to Bronze Layer format'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='sample_data/bronze_sample_transactions.json',
        help='Path to input NDJSON file (default: sample_data/bronze_sample_transactions.json)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./data_output',
        help='Output directory for transformed data (default: ./data_output)'
    )
    parser.add_argument(
        '--format',
        type=str,
        choices=['json', 'parquet'],
        default='json',
        help='Output format: "json" for compressed NDJSON or "parquet" (default: json)'
    )
    
    args = parser.parse_args()
    
    try:
        # Validate input file exists
        if not os.path.exists(args.input):
            raise FileNotFoundError(f"Input file not found: {args.input}")
        
        print(f"📖 Reading {args.input}...")
        records = read_ndjson(args.input)
        print(f"✓ Loaded {len(records)} records")
        
        print(f"🔄 Transforming records...")
        df = transform_records(records)
        print(f"✓ Transformed {len(df)} records")
        
        print(f"💾 Saving as {args.format.upper()} to {args.output_dir}...")
        partition_path = create_bronze_directory_structure(
            df, 
            args.output_dir, 
            format=args.format
        )
        
        print(f"\n✅ Success!")
        print(f"📂 Directory structure created:")
        print(f"   {partition_path}/")
        print(f"\n📊 Sample data (first 3 rows):")
        print(df.head(3).to_string(index=False))
        print(f"\n📈 Total records: {len(df)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)


if __name__ == '__main__':
    main()
