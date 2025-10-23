"""
SageMaker Inference Script
Author: Patrick Cheung

Inference handler for SageMaker Serverless Endpoint.
"""

import json
import joblib
import numpy as np
import os


def model_fn(model_dir):
    """
    Load model from model_dir
    """
    model_path = os.path.join(model_dir, 'fraud_model.pkl')
    model = joblib.load(model_path)
    return model


def input_fn(request_body, request_content_type):
    """
    Parse input data
    """
    if request_content_type == 'application/json':
        data = json.loads(request_body)
        
        # Support both single prediction and batch
        if isinstance(data, dict):
            # Single prediction
            features = [
                data.get('txn_count_1h', 0),
                data.get('txn_amount_1h', 0),
                data.get('merchant_count_24h', 0),
                data.get('avg_amount_7d', 0),
                data.get('amount', 0)
            ]
            return np.array([features])
        elif isinstance(data, list):
            # Batch prediction
            features_list = []
            for item in data:
                features = [
                    item.get('txn_count_1h', 0),
                    item.get('txn_amount_1h', 0),
                    item.get('merchant_count_24h', 0),
                    item.get('avg_amount_7d', 0),
                    item.get('amount', 0)
                ]
                features_list.append(features)
            return np.array(features_list)
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data, model):
    """
    Make predictions
    """
    predictions = model.predict(input_data)
    probabilities = model.predict_proba(input_data)
    
    return {
        'predictions': predictions.tolist(),
        'probabilities': probabilities.tolist()
    }


def output_fn(prediction, response_content_type):
    """
    Format output
    """
    if response_content_type == 'application/json':
        # Format response
        results = []
        for i, (pred, prob) in enumerate(zip(
            prediction['predictions'], 
            prediction['probabilities']
        )):
            results.append({
                'is_fraud': int(pred),
                'fraud_probability': float(prob[1]),
                'confidence': float(max(prob))
            })
        
        # Return single result or batch
        if len(results) == 1:
            return json.dumps(results[0])
        else:
            return json.dumps(results)
    else:
        raise ValueError(f"Unsupported response type: {response_content_type}")
