"""
Register SageMaker Feature Groups
Author: Patrick Cheung

Creates and configures SageMaker Feature Groups for the project.
"""

import boto3
import time
from botocore.exceptions import ClientError


def create_feature_group(
    feature_group_name,
    record_identifier_name,
    event_time_feature_name,
    feature_definitions,
    s3_uri,
    role_arn,
    region="ap-southeast-1"
):
    """
    Create a SageMaker Feature Group with Online and Offline store
    """
    client = boto3.client("sagemaker", region_name=region)
    
    try:
        # Check if feature group already exists
        try:
            response = client.describe_feature_group(FeatureGroupName=feature_group_name)
            print(f"Feature Group '{feature_group_name}' already exists")
            return response
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFound":
                raise
        
        # Create feature group
        print(f"Creating Feature Group: {feature_group_name}")
        response = client.create_feature_group(
            FeatureGroupName=feature_group_name,
            RecordIdentifierFeatureName=record_identifier_name,
            EventTimeFeatureName=event_time_feature_name,
            FeatureDefinitions=feature_definitions,
            OnlineStoreConfig={"EnableOnlineStore": True},
            OfflineStoreConfig={
                "S3StorageConfig": {"S3Uri": s3_uri},
                "DisableGlueTableCreation": False
            },
            RoleArn=role_arn,
            Description="Real-time card transaction features for fraud detection"
        )
        
        print(f"Feature Group created: {response['FeatureGroupArn']}")
        
        # Wait for feature group to be created
        print("Waiting for Feature Group to be created...")
        while True:
            status_response = client.describe_feature_group(
                FeatureGroupName=feature_group_name
            )
            status = status_response["FeatureGroupStatus"]
            
            if status == "Created":
                print("Feature Group is ready")
                break
            elif status == "CreateFailed":
                raise Exception("Feature Group creation failed")
            
            print(f"Status: {status}, waiting...")
            time.sleep(10)
        
        return response
        
    except Exception as e:
        print(f"Error creating feature group: {e}")
        raise


def main():
    """
    Main function to register feature groups
    """
    # Feature definitions for card transaction features
    feature_definitions = [
        {"FeatureName": "card_id", "FeatureType": "String"},
        {"FeatureName": "event_id", "FeatureType": "String"},
        {"FeatureName": "merchant_id", "FeatureType": "String"},
        {"FeatureName": "amount", "FeatureType": "Fractional"},
        {"FeatureName": "currency", "FeatureType": "String"},
        {"FeatureName": "country", "FeatureType": "String"},
        {"FeatureName": "pos_mode", "FeatureType": "String"},
        {"FeatureName": "event_time", "FeatureType": "Fractional"},
        {"FeatureName": "txn_count_1h", "FeatureType": "Integral"},
        {"FeatureName": "txn_amount_1h", "FeatureType": "Fractional"},
        {"FeatureName": "merchant_count_24h", "FeatureType": "Integral"},
        {"FeatureName": "avg_amount_7d", "FeatureType": "Fractional"}
    ]
    
    # Configuration (should be passed as arguments or from environment)
    feature_group_name = "rt_card_features_v1"
    s3_bucket = "your-datalake-bucket"  # Replace with actual bucket
    s3_uri = f"s3://{s3_bucket}/feature-store/offline"
    role_arn = "arn:aws:iam::ACCOUNT_ID:role/SageMakerFeatureStoreRole"  # Replace
    
    # Create feature group
    create_feature_group(
        feature_group_name=feature_group_name,
        record_identifier_name="card_id",
        event_time_feature_name="event_time",
        feature_definitions=feature_definitions,
        s3_uri=s3_uri,
        role_arn=role_arn
    )
    
    print("Feature Group registration completed")


if __name__ == "__main__":
    main()
