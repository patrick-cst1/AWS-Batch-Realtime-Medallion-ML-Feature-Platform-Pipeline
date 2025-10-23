# SageMaker Serverless Inference & Model Monitor 指南

簡單 demo 版本，快速設定 real-time inference 同 data drift detection。

---

## 快速開始

### 前置條件

```bash
# 1. 安裝 dependencies
pip install sagemaker scikit-learn boto3 pandas joblib

# 2. 確保有以下 AWS resources
# - S3 bucket for model artifacts
# - IAM role with SageMaker permissions
# - AWS credentials configured
```

### 完整流程（5 個步驟）

```bash
# Step 1: 訓練 model
cd models
python train_fraud_model.py

# Step 2: Deploy Serverless Endpoint
python deploy_serverless.py \
  --bucket your-bucket-name \
  --role-arn arn:aws:iam::ACCOUNT:role/SageMakerRole \
  --endpoint-name fraud-detection-serverless

# Step 3: 測試 endpoint
python test_endpoint.py \
  --endpoint-name fraud-detection-serverless \
  --generate-traffic

# Step 4: 設定 Model Monitor (等 endpoint 部署完成後)
python setup_model_monitor.py \
  --endpoint-name fraud-detection-serverless \
  --bucket your-bucket-name \
  --role-arn arn:aws:iam::ACCOUNT:role/SageMakerRole \
  --skip-data-capture

# Step 5: 檢查 drift (等待 1+ 小時後)
python check_drift.py \
  --endpoint-name fraud-detection-serverless \
  --bucket your-bucket-name
```

---

## 詳細說明

### 1. 訓練 Model

```bash
python train_fraud_model.py
```

**輸出**:
- `models/artifacts/fraud_model.pkl` - Trained model
- `models/artifacts/feature_names.json` - Feature definitions
- `models/artifacts/baseline_stats.json` - Baseline statistics
- `models/artifacts/test_data.csv` - Test data for monitoring

**Model Details**:
- Algorithm: RandomForest (100 trees)
- Features: 5 (txn_count_1h, txn_amount_1h, merchant_count_24h, avg_amount_7d, amount)
- Target: Binary classification (fraud/not fraud)

---

### 2. Deploy Serverless Endpoint

```bash
python deploy_serverless.py \
  --bucket my-ml-bucket \
  --role-arn arn:aws:iam::123456789012:role/SageMakerRole \
  --endpoint-name fraud-detection-serverless \
  --region ap-southeast-1
```

**配置**:
- Memory: 2GB (足夠 demo)
- Max Concurrency: 5 requests
- Cold start: ~10 seconds (第一次 request)
- Warm latency: ~100ms

**成本** (ap-southeast-1):
- Compute: $0.000067 per second
- 例子: 1000 requests/day × 0.1s = $2/month

**等待時間**: 5-10 分鐘

---

### 3. 測試 Endpoint

#### 單一 Prediction

```bash
python test_endpoint.py --endpoint-name fraud-detection-serverless
```

**Example Request**:
```json
{
  "txn_count_1h": 2,
  "txn_amount_1h": 150.0,
  "merchant_count_24h": 3,
  "avg_amount_7d": 120.0,
  "amount": 75.0
}
```

**Example Response**:
```json
{
  "is_fraud": 0,
  "fraud_probability": 0.1234,
  "confidence": 0.8766
}
```

#### 生成測試流量（用於 Model Monitor）

```bash
python test_endpoint.py \
  --endpoint-name fraud-detection-serverless \
  --generate-traffic \
  --num-requests 50
```

---

### 4. 設定 Model Monitor

#### Option A: 部署時 enable data capture (推薦)

修改 `deploy_serverless.py` 加入 data capture:

```python
from sagemaker.model_monitor import DataCaptureConfig

data_capture_config = DataCaptureConfig(
    enable_capture=True,
    sampling_percentage=100,
    destination_s3_uri=f's3://{bucket}/model-monitor/data-capture'
)

predictor = model.deploy(
    serverless_inference_config=serverless_config,
    endpoint_name=endpoint_name,
    data_capture_config=data_capture_config  # ← Add this
)
```

#### Option B: 現有 endpoint 設定 monitoring

```bash
# 等 endpoint 部署完成後
python setup_model_monitor.py \
  --endpoint-name fraud-detection-serverless \
  --bucket my-ml-bucket \
  --role-arn arn:aws:iam::123456789012:role/SageMakerRole \
  --skip-data-capture
```

**What it does**:
1. 上傳 baseline data 到 S3
2. 生成 baseline statistics & constraints
3. 建立 hourly monitoring schedule
4. 設定 CloudWatch alarms

**等待時間**: 5-10 分鐘 (baseline generation)

---

### 5. 檢查 Drift

```bash
# 等待至少 1 小時 (monitoring job 執行後)
python check_drift.py \
  --endpoint-name fraud-detection-serverless \
  --bucket my-ml-bucket
```

**輸出**:
- Monitoring schedule status
- Recent drift reports
- Violation details
- CloudWatch metrics

---

## 使用場景

### Scenario 1: 整合 Feature Store

```python
import boto3
from feature_store.ingest_features import FeatureStoreIngester

# 1. Get features from Feature Store
ingester = FeatureStoreIngester("rt_card_features_v1")
features = ingester.get_record("card_001")

# 2. Prepare for prediction
prediction_input = {
    "txn_count_1h": features['txn_count_1h'],
    "txn_amount_1h": features['txn_amount_1h'],
    "merchant_count_24h": features['merchant_count_24h'],
    "avg_amount_7d": features['avg_amount_7d'],
    "amount": current_transaction['amount']
}

# 3. Invoke endpoint
runtime = boto3.client('sagemaker-runtime')
response = runtime.invoke_endpoint(
    EndpointName='fraud-detection-serverless',
    ContentType='application/json',
    Body=json.dumps(prediction_input)
)

result = json.loads(response['Body'].read())

# 4. Decision
if result['fraud_probability'] > 0.7:
    action = "DECLINE"
else:
    action = "APPROVE"
```

### Scenario 2: Batch Predictions

```python
# Prepare batch
transactions = [
    {"txn_count_1h": 1, "txn_amount_1h": 50, ...},
    {"txn_count_1h": 10, "txn_amount_1h": 5000, ...},
    {"txn_count_1h": 3, "txn_amount_1h": 300, ...}
]

# Invoke endpoint
response = runtime.invoke_endpoint(
    EndpointName='fraud-detection-serverless',
    ContentType='application/json',
    Body=json.dumps(transactions)
)

results = json.loads(response['Body'].read())

# Process results
for txn, result in zip(transactions, results):
    print(f"Txn Amount: {txn['amount']}, "
          f"Fraud Prob: {result['fraud_probability']:.2f}")
```

### Scenario 3: 檢測 Drift 並 Retrain

```python
# Check drift report
import json
import boto3

s3 = boto3.client('s3')
response = s3.get_object(
    Bucket='my-bucket',
    Key='model-monitor/reports/fraud-detection/latest/constraint_violations.json'
)

violations = json.loads(response['Body'].read())

if len(violations.get('violations', [])) > 0:
    print("⚠️ Drift detected! Retraining recommended.")
    
    # Trigger retraining pipeline
    # 1. Backfill latest features
    # 2. Extract training data from Feature Store
    # 3. Retrain model
    # 4. Deploy new version
```

---

## Drift Detection 詳情

### Model Monitor 檢測咩？

#### 1. Feature Drift (Distribution Changes)

**Example**:
```
Baseline (training data):
  txn_count_1h: mean=3.2, std=2.1

Current (production):
  txn_count_1h: mean=7.5, std=3.8

→ Drift detected! (mean shifted significantly)
```

#### 2. Data Quality Issues

- Missing values
- Null rate increase
- Outliers
- Invalid ranges

#### 3. Schema Violations

- Missing features
- Wrong data types
- New unexpected features

### Drift Thresholds

**Default Constraints**:
```json
{
  "txn_count_1h": {
    "mean_constraint": {
      "baseline_mean": 3.2,
      "std_dev": 2.1,
      "threshold_stddev": 3
    }
  }
}
```

**Violation Example**:
```json
{
  "feature_name": "txn_count_1h",
  "constraint_check_type": "baseline_drift_check",
  "description": "Mean value drifted beyond 3 standard deviations"
}
```

---

## Monitoring Schedule

### Hourly Monitoring Job

```
Every hour:
1. Collect captured data from S3
2. Calculate statistics
3. Compare with baseline
4. Generate violation report
5. Publish CloudWatch metrics
```

### CloudWatch Metrics

**Namespace**: `aws/sagemaker/Endpoints/data-metrics`

**Metrics**:
- `feature_baseline_drift_<feature_name>`: Drift magnitude
- `feature_baseline_drift`: Overall drift score

**View in Console**:
```
CloudWatch → Metrics → aws/sagemaker/Endpoints/data-metrics
→ Filter by Endpoint: fraud-detection-serverless
```

---

## Cost Breakdown (Demo)

| Component | Configuration | Estimated Cost |
|-----------|--------------|----------------|
| **Serverless Endpoint** | 2GB, 100 requests/day | $2/month |
| **Data Capture** | S3 storage | $0.50/month |
| **Monitoring Jobs** | 1 job/hour, ml.m5.xlarge | $40/month |
| **S3 Reports** | 720 reports/month | $0.10/month |
| **CloudWatch** | Metrics & logs | $5/month |
| **Total** | | **~$48/month** |

**省錢 Tips**:
- 減少 monitoring frequency (e.g., daily instead of hourly)
- 降低 data capture sampling (e.g., 10% instead of 100%)
- 用細啲嘅 monitoring instance (ml.m5.large)

---

## Troubleshooting

### Issue 1: Endpoint Cold Start Slow

**症狀**: First request takes 10-20 seconds

**解決**:
- Serverless endpoints 有 cold start (正常)
- Subsequent requests fast (~100ms)
- For consistently low latency, use standard endpoint

### Issue 2: No Monitoring Data

**症狀**: No drift reports generated

**Causes**:
1. Data capture 未 enable
2. 未有足夠 traffic (需要至少幾個 requests)
3. Monitoring job 未執行

**Debug**:
```bash
# Check data capture
aws s3 ls s3://my-bucket/model-monitor/data-capture/

# Check monitoring executions
aws sagemaker list-monitoring-executions \
  --monitoring-schedule-name fraud-detection-serverless-monitor
```

### Issue 3: Baseline Generation Failed

**症狀**: Baseline job failed

**Solutions**:
```bash
# Check job logs
aws sagemaker describe-processing-job \
  --processing-job-name <job-name>

# Common fix: Ensure baseline data is valid CSV with headers
```

---

## Cleanup

### Delete Endpoint

```bash
aws sagemaker delete-endpoint --endpoint-name fraud-detection-serverless
aws sagemaker delete-endpoint-config --endpoint-config-name fraud-detection-serverless-config
aws sagemaker delete-model --model-name fraud-detection-serverless-model
```

### Delete Monitoring

```bash
aws sagemaker delete-monitoring-schedule \
  --monitoring-schedule-name fraud-detection-serverless-monitor
```

### Delete S3 Data

```bash
aws s3 rm s3://my-bucket/model-monitor/ --recursive
aws s3 rm s3://my-bucket/models/ --recursive
```

---

## 進階配置

### 調整 Serverless Config

```python
# Higher memory for complex models
ServerlessInferenceConfig(
    memory_size_in_mb=4096,  # 4GB
    max_concurrency=20       # More concurrent requests
)
```

### 自定義 Drift Thresholds

```python
# Modify baseline constraints
constraints = json.load(open('baseline_constraints.json'))

# Adjust threshold
constraints['features'][0]['mean_constraint']['threshold_stddev'] = 2.0  # Stricter

# Save and use in monitoring schedule
```

### 整合 SNS Alerts

```python
# Add SNS topic to CloudWatch alarm
cloudwatch.put_metric_alarm(
    AlarmName='fraud-model-drift-alert',
    AlarmActions=[
        'arn:aws:sns:ap-southeast-1:123456:model-alerts'
    ],
    # ... other parameters
)
```

---

## 參考資料

- [SageMaker Serverless Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html)
- [SageMaker Model Monitor](https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor.html)
- [Data Capture](https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor-data-capture.html)

---

**Last Updated**: 2025-10-20  
**Author**: Patrick Cheung
