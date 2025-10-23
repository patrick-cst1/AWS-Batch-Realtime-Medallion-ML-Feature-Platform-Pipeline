# 🧪 End-to-End Testing Guide

This guide teaches you how to test the complete **Realtime Medallion ML Feature Platform Pipeline**, from uploading sample data to observing results.

## 📋 Prerequisites

- ✅ Infrastructure deployed (via GitHub Actions)
- ✅ Terraform outputs available (bucket names, ARNs)
- ✅ AWS CLI configured
- ✅ Python environment with dependencies

## 🎯 Testing Process Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 1. Upload   │ -> │ 2. Trigger  │ -> │ 3. Monitor  │ -> │ 4. Verify   │
│ Sample Data │    │ Pipeline    │    │ Processing │    │ Results     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## 1️⃣ Prepare Sample Data

### Step 1.1: Transform Sample Data Locally

```powershell
# Ensure you're in the project root
cd d:\Data_Project_Repo\AWS-Batch-Realtime-Medallion-ML-Feature-Platform-Pipeline

# Transform sample data to Bronze format
python scripts/transform_and_prepare_sample_data.py

# You should see:
# 📖 Reading sample_data/bronze_sample_transactions.json...
# ✓ Loaded 20 records
# 🔄 Transforming records...
# ✓ Transformed 20 records
# 💾 Saving as JSON to ./data_output...
# ✓ Saved compressed JSON: ./data_output/bronze/streaming/card_authorization/ingest_dt=2025/10/23/16/30/data.json.gz
# ✅ Success!
```

### Step 1.2: Upload to S3 Bronze Layer

```powershell
# Get your bucket name from Terraform outputs
$DATALAKE_BUCKET = "your-datalake-bucket-name"  # From terraform output

# Upload the transformed data
aws s3 cp ./data_output/bronze/streaming/card_authorization/ingest_dt=2025/10/23/16/30/data.json.gz `
  s3://$DATALAKE_BUCKET/bronze/streaming/card_authorization/ingest_dt=2025/10/23/16/30/data.json.gz `
  --region ap-southeast-1

# Verify upload
aws s3 ls s3://$DATALAKE_BUCKET/bronze/streaming/card_authorization/ingest_dt=2025/10/23/16/30/
```

---

## 2️⃣ Trigger Streaming Pipeline

### Step 2.1: Prepare Parameters

```powershell
# Get values from Terraform outputs
$SFN_ARN = "arn:aws:states:ap-southeast-1:ACCOUNT:stateMachine:stream-pipeline"
$APP_ID = "your-emr-application-id"
$DATA_BUCKET = "your-datalake-bucket-name"
$CODE_BUCKET = "your-code-bucket-name"
$EMR_JOB_ROLE = "arn:aws:iam::ACCOUNT:role/your-emr-job-role"

# Current timestamp
$NOW = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
```

### Step 2.2: Trigger Step Functions (Stream Mode)

```powershell
aws stepfunctions start-execution `
  --state-machine-arn $SFN_ARN `
  --input "{
    \"mode\":\"stream\",
    \"now\":\"$NOW\",
    \"bucket\":\"$DATA_BUCKET\",
    \"codeBucket\":\"$CODE_BUCKET\",
    \"bronzePrefix\":\"bronze/streaming\",
    \"silverPrefix\":\"silver\",
    \"goldPrefix\":\"gold\",
    \"featureGroup\":\"rt_card_features_v1\",
    \"emr\":{
      \"appId\":\"$APP_ID\",
      \"jobRole\":\"$EMR_JOB_ROLE\"
    }
  }" `
  --region ap-southeast-1
```

### Step 2.3: Record Execution ARN

```powershell
# Command output will show:
# {
#     "executionArn": "arn:aws:states:ap-southeast-1:ACCOUNT:execution:stream-pipeline:xxxxx",
#     "startDate": "2025-10-24T10:00:00.000Z"
# }

$EXECUTION_ARN = "arn:aws:states:ap-southeast-1:ACCOUNT:execution:stream-pipeline:xxxxx"
```

---

## 3️⃣ Monitor Pipeline Execution

### Step 3.1: Monitor Step Functions

```powershell
# Check execution status
aws stepfunctions describe-execution --execution-arn $EXECUTION_ARN --region ap-southeast-1

# Should see: "status": "RUNNING" then "SUCCEEDED"
```

### Step 3.2: Monitor EMR Serverless Job

```powershell
# Get EMR job details from Step Functions
aws stepfunctions get-execution-history --execution-arn $EXECUTION_ARN --region ap-southeast-1

# Find the EMR job ID in the history, then check:
aws emr-serverless get-job-run --application-id $APP_ID --job-run-id $JOB_RUN_ID --region ap-southeast-1
```

### Step 3.3: Monitor CloudWatch Logs

```powershell
# EMR Serverless logs
aws logs tail /aws/emr-serverless/applications/$APP_ID/jobs/$JOB_RUN_ID --region ap-southeast-1 --follow

# Step Functions logs
aws logs tail /aws/states/stream-pipeline/$EXECUTION_ARN --region ap-southeast-1 --follow
```

### Step 3.4: Monitor CloudWatch Dashboard

```powershell
# Open dashboard in browser
$DASHBOARD_URL = "https://ap-southeast-1.console.aws.amazon.com/cloudwatch/home?region=ap-southeast-1#dashboards:name=your-project-dev-dashboard"
Start-Process $DASHBOARD_URL
```

---

## 4️⃣ Verify Pipeline Results

### Step 4.1: Check S3 Outputs

```powershell
# Check Silver layer (cleaned data)
aws s3 ls s3://$DATA_BUCKET/silver/card_transactions/ --recursive --region ap-southeast-1

# Check Gold layer (features)
aws s3 ls s3://$DATA_BUCKET/gold/card_features/ --recursive --region ap-southeast-1

# Sample Gold data
aws s3 cp s3://$DATA_BUCKET/gold/card_features/dt=2025-10-24/part-00000-xxx.parquet - --region ap-southeast-1 | head -20
```

### Step 4.2: Check Feature Store

#### Online Store (DynamoDB)
```powershell
# Check if records exist in Online Store
aws sagemaker get-record `
  --feature-group-name rt_card_features_v1 `
  --record-identifier-value-as-string "card_00001" `
  --region ap-southeast-1
```

#### Offline Store (S3)
```powershell
# Check Offline Store data
aws s3 ls s3://sagemaker-ap-southeast-1-ACCOUNT-offline-store/rt_card_features_v1/ --recursive --region ap-southeast-1
```

### Step 4.3: Check Glue Catalog

```powershell
# Check if table was created
aws glue get-table --database-name sagemaker_featurestore --name rt_card_features_v1 --region ap-southeast-1

# Query via Athena
aws athena start-query-execution `
  --query-string "SELECT * FROM rt_card_features_v1 LIMIT 10" `
  --query-execution-context Database=sagemaker_featurestore `
  --result-configuration OutputLocation=s3://$DATA_BUCKET/athena-results/ `
  --region ap-southeast-1
```

---

## 5️⃣ Test Daily Batch Pipeline

### Step 5.1: Trigger Daily Mode

```powershell
aws stepfunctions start-execution `
  --state-machine-arn $SFN_ARN `
  --input "{
    \"mode\":\"daily\",
    \"bucket\":\"$DATA_BUCKET\",
    \"codeBucket\":\"$CODE_BUCKET\",
    \"goldPrefix\":\"gold\",
    \"trainingPrefix\":\"gold/training\",
    \"inferencePrefix\":\"gold/inference\",
    \"emr\":{
      \"appId\":\"$APP_ID\",
      \"jobRole\":\"$EMR_JOB_ROLE\"
    }
  }" `
  --region ap-southeast-1
```

### Step 5.2: Check Training/Inference Datasets

```powershell
# Check training datasets
aws s3 ls s3://$DATA_BUCKET/gold/training/ --recursive --region ap-southeast-1

# Check inference datasets
aws s3 ls s3://$DATA_BUCKET/gold/inference/ --recursive --region ap-southeast-1

# Sample training data
aws s3 cp s3://$DATA_BUCKET/gold/training/dt=2025-10-24/train/part-00000-xxx.parquet - --region ap-southeast-1 | head -10
```

---

## 📊 Key Observations

### ✅ Success Indicators

| Component | Expected | Check Method |
|-----------|----------|--------------|
| **S3 Bronze** | `data.json.gz` | `aws s3 ls s3://bucket/bronze/...` |
| **S3 Silver** | `*.parquet` files | `aws s3 ls s3://bucket/silver/...` |
| **S3 Gold** | `*.parquet` with features | `aws s3 ls s3://bucket/gold/...` |
| **Online Store** | Records retrievable | `aws sagemaker get-record` |
| **Offline Store** | S3 files | `aws s3 ls sagemaker-*-offline-store/` |
| **Glue Catalog** | Table exists | `aws glue get-table` |
| **Training Data** | Train/val split | `aws s3 ls s3://bucket/gold/training/` |
| **Inference Data** | Latest features | `aws s3 ls s3://bucket/gold/inference/` |

### 🔍 Critical Metrics

```powershell
# CloudWatch metrics to monitor
aws cloudwatch get-metric-statistics `
  --namespace "P1Unified" `
  --metric-name "StreamPipelineSuccess" `
  --start-time 2025-10-24T00:00:00Z `
  --end-time 2025-10-24T23:59:59Z `
  --period 3600 `
  --statistics Sum `
  --region ap-southeast-1
```

### 🚨 Common Issues

#### EMR Job Failure
```powershell
# Check EMR logs
aws logs tail /aws/emr-serverless/applications/$APP_ID/jobs/$JOB_RUN_ID --region ap-southeast-1

# Common issues:
# - S3 permissions
# - Spark code syntax errors
# - Feature Group not created
```

#### No Data in Feature Store
```powershell
# Check Feature Group status
aws sagemaker describe-feature-group --feature-group-name rt_card_features_v1 --region ap-southeast-1

# Should be "FeatureGroupStatus": "Created"
```

#### Step Functions Stuck
```powershell
# Check execution history
aws stepfunctions get-execution-history --execution-arn $EXECUTION_ARN --region ap-southeast-1
```

---

## 🎯 Complete Testing Script

```powershell
# One-liner test script (save as test_pipeline.ps1)
param(
    [string]$DataBucket,
    [string]$CodeBucket,
    [string]$EmrAppId,
    [string]$EmrJobRole,
    [string]$StepFunctionArn
)

Write-Host "🚀 Starting Pipeline Test..."

# 1. Transform and upload data
Write-Host "📤 Uploading sample data..."
python scripts/transform_and_prepare_sample_data.py
aws s3 cp ./data_output/bronze/streaming/card_authorization/ingest_dt=2025/10/23/16/30/data.json.gz s3://$DataBucket/bronze/streaming/card_authorization/ingest_dt=2025/10/23/16/30/data.json.gz --region ap-southeast-1

# 2. Trigger stream pipeline
Write-Host "⚡ Triggering stream pipeline..."
$now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$result = aws stepfunctions start-execution --state-machine-arn $StepFunctionArn --input "{\"mode\":\"stream\",\"now\":\"$now\",\"bucket\":\"$DataBucket\",\"codeBucket\":\"$CodeBucket\",\"bronzePrefix\":\"bronze/streaming\",\"silverPrefix\":\"silver\",\"goldPrefix\":\"gold\",\"featureGroup\":\"rt_card_features_v1\",\"emr\":{\"appId\":\"$EmrAppId\",\"jobRole\":\"$EmrJobRole\"}}" --region ap-southeast-1 | ConvertFrom-Json
$executionArn = $result.executionArn

# 3. Monitor execution
Write-Host "👀 Monitoring execution: $executionArn"
do {
    $status = aws stepfunctions describe-execution --execution-arn $executionArn --region ap-southeast-1 | ConvertFrom-Json
    Write-Host "Status: $($status.status)"
    Start-Sleep -Seconds 30
} while ($status.status -eq "RUNNING")

# 4. Check results
Write-Host "✅ Checking results..."
aws s3 ls s3://$DataBucket/gold/card_features/ --recursive --region ap-southeast-1
aws sagemaker get-record --feature-group-name rt_card_features_v1 --record-identifier-value-as-string "card_00001" --region ap-southeast-1

Write-Host "🎉 Pipeline test complete!"
```

---

## 💰 Cost Monitoring

```powershell
# Check costs (CloudWatch)
aws cloudwatch get-metric-statistics `
  --namespace "AWS/Billing" `
  --metric-name "EstimatedCharges" `
  --dimensions Name=ServiceName,Value=AmazonSageMaker Name=ServiceName,Value=EMRServerless `
  --start-time 2025-10-24T00:00:00Z `
  --end-time 2025-10-24T23:59:59Z `
  --period 3600 `
  --statistics Maximum `
  --region us-east-1
```

---

## 🧹 Cleanup

```powershell
# Clean up test data
aws s3 rm s3://$DATA_BUCKET/bronze/streaming/card_authorization/ --recursive --region ap-southeast-1
aws s3 rm s3://$DATA_BUCKET/silver/ --recursive --region ap-southeast-1
aws s3 rm s3://$DATA_BUCKET/gold/ --recursive --region ap-southeast-1

# Remove local test files
Remove-Item -Path ./data_output -Recurse -Force
```

---

**🎯 Summary**: Follow steps 1-4 for complete end-to-end testing. Monitor CloudWatch and check S3 outputs at each stage!