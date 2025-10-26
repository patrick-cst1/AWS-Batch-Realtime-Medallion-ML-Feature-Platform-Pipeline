"""
Train Simple Fraud Detection Model (Demo)
Author: Patrick Cheung

Train a simple sklearn RandomForest model for fraud detection demo.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import joblib
import json
import os


def generate_synthetic_training_data(n_samples=10000):
    """
    Generate synthetic fraud detection training data
    """
    np.random.seed(42)
    
    # Generate features
    data = {
        'txn_count_1h': np.random.poisson(3, n_samples),
        'txn_amount_1h': np.random.exponential(200, n_samples),
        'merchant_count_24h': np.random.poisson(5, n_samples),
        'avg_amount_7d': np.random.normal(150, 50, n_samples),
        'amount': np.random.exponential(100, n_samples),
    }
    
    df = pd.DataFrame(data)
    
    # Generate labels (fraud logic: high amount + high frequency)
    fraud_score = (
        (df['amount'] > 500).astype(int) * 0.4 +
        (df['txn_count_1h'] > 5).astype(int) * 0.3 +
        (df['merchant_count_24h'] > 8).astype(int) * 0.3
    )
    
    # Add some randomness
    df['is_fraud'] = (fraud_score + np.random.random(n_samples) * 0.2 > 0.7).astype(int)
    
    # Imbalanced dataset (10% fraud)
    fraud_indices = df[df['is_fraud'] == 1].index
    keep_fraud = np.random.choice(fraud_indices, size=int(len(fraud_indices) * 0.1), replace=False)
    normal_indices = df[df['is_fraud'] == 0].index
    
    final_indices = np.concatenate([keep_fraud, normal_indices])
    df = df.loc[final_indices].reset_index(drop=True)
    
    return df


def train_model(output_dir='models/artifacts'):
    """
    Train fraud detection model
    """
    print("=" * 80)
    print("TRAINING FRAUD DETECTION MODEL (DEMO)")
    print("=" * 80)
    
    # Generate training data
    print("\n1. Generating synthetic training data...")
    df = generate_synthetic_training_data(n_samples=10000)
    
    print(f"   Total samples: {len(df)}")
    print(f"   Fraud ratio: {df['is_fraud'].mean():.2%}")
    
    # Split features and target
    feature_cols = ['txn_count_1h', 'txn_amount_1h', 'merchant_count_24h', 
                    'avg_amount_7d', 'amount']
    X = df[feature_cols]
    y = df['is_fraud']
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\n2. Training RandomForest model...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    print(f"\n3. Evaluating model...")
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    auc_score = roc_auc_score(y_test, y_pred_proba)
    print(f"ROC-AUC Score: {auc_score:.4f}")
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nFeature Importance:")
    print(feature_importance.to_string(index=False))
    
    # Save model
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, 'fraud_model.pkl')
    joblib.dump(model, model_path)
    print(f"\n4. Model saved to: {model_path}")
    
    # Save feature names
    feature_names_path = os.path.join(output_dir, 'feature_names.json')
    with open(feature_names_path, 'w') as f:
        json.dump(feature_cols, f)
    print(f"   Feature names saved to: {feature_names_path}")
    
    # Save baseline statistics for monitoring
    baseline_stats = {
        'txn_count_1h': {
            'mean': float(X_train['txn_count_1h'].mean()),
            'std': float(X_train['txn_count_1h'].std()),
            'min': float(X_train['txn_count_1h'].min()),
            'max': float(X_train['txn_count_1h'].max())
        },
        'txn_amount_1h': {
            'mean': float(X_train['txn_amount_1h'].mean()),
            'std': float(X_train['txn_amount_1h'].std()),
            'min': float(X_train['txn_amount_1h'].min()),
            'max': float(X_train['txn_amount_1h'].max())
        },
        'amount': {
            'mean': float(X_train['amount'].mean()),
            'std': float(X_train['amount'].std()),
            'min': float(X_train['amount'].min()),
            'max': float(X_train['amount'].max())
        }
    }
    
    baseline_path = os.path.join(output_dir, 'baseline_stats.json')
    with open(baseline_path, 'w') as f:
        json.dump(baseline_stats, f, indent=2)
    print(f"   Baseline statistics saved to: {baseline_path}")
    
    # Save test data for monitoring
    test_data_path = os.path.join(output_dir, 'test_data.csv')
    X_test.to_csv(test_data_path, index=False)
    print(f"   Test data saved to: {test_data_path}")
    
    print("\n" + "=" * 80)
    print("TRAINING COMPLETED")
    print("=" * 80)
    
    return model, feature_cols, baseline_stats


if __name__ == "__main__":
    train_model()
