"""
Test SageMaker Serverless Endpoint
Author: Patrick Cheung

Simple script to test fraud detection endpoint.
"""

import boto3
import json
import time
from datetime import datetime


def test_single_prediction(endpoint_name, region='ap-southeast-1'):
    """
    Test single prediction
    """
    print("=" * 80)
    print("TESTING SINGLE PREDICTION")
    print("=" * 80)
    
    runtime = boto3.client('sagemaker-runtime', region_name=region)
    
    # Test data (normal transaction)
    test_input_normal = {
        "txn_count_1h": 2,
        "txn_amount_1h": 150.0,
        "merchant_count_24h": 3,
        "avg_amount_7d": 120.0,
        "amount": 75.0
    }
    
    print("\nTest Input (Normal Transaction):")
    print(json.dumps(test_input_normal, indent=2))
    
    start_time = time.time()
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=json.dumps(test_input_normal)
    )
    latency = (time.time() - start_time) * 1000
    
    result = json.loads(response['Body'].read().decode())
    
    print("\nPrediction Result:")
    print(json.dumps(result, indent=2))
    print(f"\nLatency: {latency:.2f} ms")
    
    # Test suspicious transaction
    test_input_fraud = {
        "txn_count_1h": 8,
        "txn_amount_1h": 2500.0,
        "merchant_count_24h": 12,
        "avg_amount_7d": 150.0,
        "amount": 1200.0
    }
    
    print("\n" + "-" * 80)
    print("Test Input (Suspicious Transaction):")
    print(json.dumps(test_input_fraud, indent=2))
    
    start_time = time.time()
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=json.dumps(test_input_fraud)
    )
    latency = (time.time() - start_time) * 1000
    
    result = json.loads(response['Body'].read().decode())
    
    print("\nPrediction Result:")
    print(json.dumps(result, indent=2))
    print(f"\nLatency: {latency:.2f} ms")


def test_batch_prediction(endpoint_name, region='ap-southeast-1'):
    """
    Test batch prediction
    """
    print("\n" + "=" * 80)
    print("TESTING BATCH PREDICTION")
    print("=" * 80)
    
    runtime = boto3.client('sagemaker-runtime', region_name=region)
    
    # Batch of transactions
    test_batch = [
        {
            "txn_count_1h": 1,
            "txn_amount_1h": 50.0,
            "merchant_count_24h": 2,
            "avg_amount_7d": 100.0,
            "amount": 50.0
        },
        {
            "txn_count_1h": 10,
            "txn_amount_1h": 5000.0,
            "merchant_count_24h": 15,
            "avg_amount_7d": 200.0,
            "amount": 2000.0
        },
        {
            "txn_count_1h": 3,
            "txn_amount_1h": 300.0,
            "merchant_count_24h": 4,
            "avg_amount_7d": 150.0,
            "amount": 120.0
        }
    ]
    
    print(f"\nBatch Size: {len(test_batch)} transactions")
    
    start_time = time.time()
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=json.dumps(test_batch)
    )
    latency = (time.time() - start_time) * 1000
    
    results = json.loads(response['Body'].read().decode())
    
    print("\nBatch Prediction Results:")
    for i, result in enumerate(results, 1):
        print(f"\nTransaction {i}:")
        print(f"  Fraud: {result['is_fraud']}")
        print(f"  Probability: {result['fraud_probability']:.4f}")
        print(f"  Confidence: {result['confidence']:.4f}")
    
    print(f"\nBatch Latency: {latency:.2f} ms")
    print(f"Avg per transaction: {latency/len(test_batch):.2f} ms")


def generate_test_traffic(endpoint_name, num_requests=20, region='ap-southeast-1'):
    """
    Generate test traffic for Model Monitor data capture
    """
    print("\n" + "=" * 80)
    print("GENERATING TEST TRAFFIC FOR MODEL MONITOR")
    print("=" * 80)
    
    runtime = boto3.client('sagemaker-runtime', region_name=region)
    
    print(f"\nSending {num_requests} requests...")
    
    import random
    
    for i in range(num_requests):
        # Generate random transaction
        test_input = {
            "txn_count_1h": random.randint(0, 10),
            "txn_amount_1h": random.uniform(0, 1000),
            "merchant_count_24h": random.randint(1, 15),
            "avg_amount_7d": random.uniform(50, 300),
            "amount": random.uniform(10, 1500)
        }
        
        try:
            response = runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Body=json.dumps(test_input)
            )
            
            result = json.loads(response['Body'].read().decode())
            
            print(f"  Request {i+1}/{num_requests}: "
                  f"Fraud={result['is_fraud']}, "
                  f"Prob={result['fraud_probability']:.3f}")
            
            time.sleep(0.5)  # Small delay
            
        except Exception as e:
            print(f"  Request {i+1} failed: {e}")
    
    print("\n✓ Test traffic generated")
    print("Note: Data will be captured and available for monitoring in ~1 hour")


def main():
    """
    Main test workflow
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Test SageMaker endpoint")
    parser.add_argument('--endpoint-name', required=True, help='SageMaker endpoint name')
    parser.add_argument('--region', default='ap-southeast-1', help='AWS region')
    parser.add_argument('--generate-traffic', action='store_true', 
                        help='Generate test traffic for monitoring')
    parser.add_argument('--num-requests', type=int, default=20,
                        help='Number of test requests to generate')
    
    args = parser.parse_args()
    
    # Test single prediction
    test_single_prediction(args.endpoint_name, args.region)
    
    # Test batch prediction
    test_batch_prediction(args.endpoint_name, args.region)
    
    # Generate traffic if requested
    if args.generate_traffic:
        generate_test_traffic(args.endpoint_name, args.num_requests, args.region)
    
    print("\n" + "=" * 80)
    print("✓ TESTING COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()
