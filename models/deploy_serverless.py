"""
Deploy Model to SageMaker Serverless Inference
Author: Patrick Cheung

Simple deployment script for demo purposes.
"""

import boto3
import sagemaker
from sagemaker.sklearn import SKLearnModel
from sagemaker.serverless import ServerlessInferenceConfig
import json
import os
import tarfile
from datetime import datetime


def create_model_artifact(model_dir='models/artifacts', output_path='models/model.tar.gz'):
    """
    Package model artifacts for SageMaker
    """
    print("Creating model artifact...")
    
    # Create tarball
    with tarfile.open(output_path, 'w:gz') as tar:
        tar.add(os.path.join(model_dir, 'fraud_model.pkl'), arcname='fraud_model.pkl')
        tar.add(os.path.join(model_dir, 'feature_names.json'), arcname='feature_names.json')
        tar.add('models/inference.py', arcname='inference.py')
    
    print(f"✓ Model artifact created: {output_path}")
    return output_path


def upload_model_to_s3(model_path, bucket, prefix='models'):
    """
    Upload model to S3
    """
    print(f"Uploading model to S3...")
    
    s3 = boto3.client('s3')
    key = f"{prefix}/fraud-detection/model.tar.gz"
    
    s3.upload_file(model_path, bucket, key)
    
    model_uri = f"s3://{bucket}/{key}"
    print(f"✓ Model uploaded to: {model_uri}")
    
    return model_uri


def deploy_serverless_endpoint(
    model_uri,
    role_arn,
    endpoint_name='fraud-detection-serverless',
    region='ap-southeast-1'
):
    """
    Deploy model to SageMaker Serverless Inference endpoint
    """
    print("=" * 80)
    print("DEPLOYING TO SAGEMAKER SERVERLESS INFERENCE")
    print("=" * 80)
    
    session = sagemaker.Session(boto_session=boto3.Session(region_name=region))
    
    # Create SKLearn Model
    print("\n1. Creating SageMaker Model...")
    model = SKLearnModel(
        model_data=model_uri,
        role=role_arn,
        entry_point='inference.py',
        framework_version='1.2-1',  # sklearn version
        py_version='py3',
        sagemaker_session=session
    )
    
    # Serverless configuration (demo-friendly, cost-effective)
    print("\n2. Configuring Serverless Inference...")
    serverless_config = ServerlessInferenceConfig(
        memory_size_in_mb=2048,  # 2GB (min: 1024, max: 6144)
        max_concurrency=5        # Max concurrent requests (max: 200)
    )
    
    print(f"   Memory: 2048 MB")
    print(f"   Max Concurrency: 5")
    
    # Deploy
    print(f"\n3. Deploying endpoint: {endpoint_name}")
    print("   This may take 5-10 minutes...")
    
    predictor = model.deploy(
        serverless_inference_config=serverless_config,
        endpoint_name=endpoint_name
    )
    
    print("\n" + "=" * 80)
    print("✓ DEPLOYMENT COMPLETED")
    print("=" * 80)
    print(f"Endpoint Name: {endpoint_name}")
    print(f"Region: {region}")
    print("\nTest prediction:")
    print(f"  python models/test_endpoint.py --endpoint-name {endpoint_name}")
    
    return predictor


def main():
    """
    Main deployment workflow
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy fraud detection model")
    parser.add_argument('--bucket', required=True, help='S3 bucket for model artifacts')
    parser.add_argument('--role-arn', required=True, help='SageMaker execution role ARN')
    parser.add_argument('--endpoint-name', default='fraud-detection-serverless', 
                        help='Endpoint name')
    parser.add_argument('--region', default='ap-southeast-1', help='AWS region')
    
    args = parser.parse_args()
    
    # Step 1: Create model artifact
    model_path = create_model_artifact()
    
    # Step 2: Upload to S3
    model_uri = upload_model_to_s3(model_path, args.bucket)
    
    # Step 3: Deploy serverless endpoint
    predictor = deploy_serverless_endpoint(
        model_uri=model_uri,
        role_arn=args.role_arn,
        endpoint_name=args.endpoint_name,
        region=args.region
    )
    
    # Save endpoint info
    endpoint_info = {
        'endpoint_name': args.endpoint_name,
        'model_uri': model_uri,
        'deployed_at': datetime.utcnow().isoformat(),
        'region': args.region
    }
    
    with open('models/endpoint_info.json', 'w') as f:
        json.dump(endpoint_info, f, indent=2)
    
    print(f"\nEndpoint info saved to: models/endpoint_info.json")


if __name__ == "__main__":
    main()
