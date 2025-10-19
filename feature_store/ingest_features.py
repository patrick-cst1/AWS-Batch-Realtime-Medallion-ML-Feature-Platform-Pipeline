"""
Ingest Features to SageMaker Feature Store
Author: Patrick Cheung

Utility functions for upserting features to Feature Store.
"""

import boto3
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime


class FeatureStoreIngester:
    """
    Helper class for ingesting features to SageMaker Feature Store
    """
    
    def __init__(self, feature_group_name: str, region: str = "ap-southeast-1"):
        self.feature_group_name = feature_group_name
        self.region = region
        self.client = boto3.client("sagemaker-featurestore-runtime", region_name=region)
        self.sagemaker_client = boto3.client("sagemaker", region_name=region)
        
        # Get feature group metadata
        self.feature_group_info = self.sagemaker_client.describe_feature_group(
            FeatureGroupName=feature_group_name
        )
        self.feature_names = [
            fd["FeatureName"] for fd in self.feature_group_info["FeatureDefinitions"]
        ]
    
    def prepare_record(self, row: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Prepare a single record for Feature Store ingestion
        """
        record = []
        for feature_name in self.feature_names:
            if feature_name in row:
                value = row[feature_name]
                record.append({
                    "FeatureName": feature_name,
                    "ValueAsString": str(value)
                })
        return record
    
    def put_record(self, record: Dict[str, Any]):
        """
        Ingest a single record to Feature Store
        """
        prepared_record = self.prepare_record(record)
        
        try:
            response = self.client.put_record(
                FeatureGroupName=self.feature_group_name,
                Record=prepared_record
            )
            return response
        except Exception as e:
            print(f"Error ingesting record: {e}")
            raise
    
    def batch_put_records(self, records: List[Dict[str, Any]], batch_size: int = 100):
        """
        Ingest multiple records to Feature Store in batches
        """
        total_records = len(records)
        success_count = 0
        error_count = 0
        
        print(f"Starting batch ingestion of {total_records} records")
        
        for i in range(0, total_records, batch_size):
            batch = records[i:i + batch_size]
            prepared_batch = [
                {"Record": self.prepare_record(record)} for record in batch
            ]
            
            try:
                response = self.client.batch_put_record(
                    FeatureGroupName=self.feature_group_name,
                    Records=prepared_batch
                )
                
                # Check for errors in response
                if "Errors" in response and response["Errors"]:
                    error_count += len(response["Errors"])
                    print(f"Batch {i//batch_size + 1}: {len(response['Errors'])} errors")
                else:
                    success_count += len(batch)
                    print(f"Batch {i//batch_size + 1}: {len(batch)} records ingested")
                
            except Exception as e:
                print(f"Error in batch {i//batch_size + 1}: {e}")
                error_count += len(batch)
        
        print(f"Ingestion complete: {success_count} success, {error_count} errors")
        return {"success": success_count, "errors": error_count}
    
    def ingest_from_dataframe(self, df: pd.DataFrame, batch_size: int = 100):
        """
        Ingest features from a Pandas DataFrame
        """
        records = df.to_dict("records")
        return self.batch_put_records(records, batch_size)
    
    def get_record(self, record_identifier_value: str):
        """
        Retrieve a single record from Feature Store Online Store
        """
        record_identifier_name = self.feature_group_info["RecordIdentifierFeatureName"]
        
        try:
            response = self.client.get_record(
                FeatureGroupName=self.feature_group_name,
                RecordIdentifierValueAsString=record_identifier_value,
                FeatureNames=self.feature_names
            )
            return response.get("Record", [])
        except Exception as e:
            print(f"Error retrieving record: {e}")
            return None
    
    def batch_get_records(self, record_identifiers: List[str]):
        """
        Retrieve multiple records from Feature Store Online Store
        """
        record_identifier_name = self.feature_group_info["RecordIdentifierFeatureName"]
        
        identifiers = [
            {
                "FeatureGroupName": self.feature_group_name,
                "RecordIdentifiersValueAsString": record_identifiers,
                "FeatureNames": self.feature_names
            }
        ]
        
        try:
            response = self.client.batch_get_record(Identifiers=identifiers)
            return response.get("Records", [])
        except Exception as e:
            print(f"Error retrieving records: {e}")
            return []


def main():
    """
    Example usage of FeatureStoreIngester
    """
    # Initialize ingester
    ingester = FeatureStoreIngester(feature_group_name="rt_card_features_v1")
    
    # Example: Ingest sample records
    sample_records = [
        {
            "card_id": "card_001",
            "event_id": "evt_001",
            "merchant_id": "merch_001",
            "amount": 100.50,
            "currency": "USD",
            "country": "US",
            "pos_mode": "chip",
            "event_time": datetime.utcnow().timestamp(),
            "txn_count_1h": 3,
            "txn_amount_1h": 250.75,
            "merchant_count_24h": 5,
            "avg_amount_7d": 150.25
        }
    ]
    
    # Ingest records
    result = ingester.batch_put_records(sample_records)
    print(f"Ingestion result: {result}")
    
    # Retrieve record
    record = ingester.get_record("card_001")
    print(f"Retrieved record: {record}")


if __name__ == "__main__":
    main()
