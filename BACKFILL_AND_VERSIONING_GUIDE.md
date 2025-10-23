# Backfill & Feature Versioning 指南

本指南說明如何進行歷史數據 backfill 以及如何管理 feature versions。

---

## 目錄

1. [Feature Versioning 概念](#feature-versioning-概念)
2. [Backfilling 概念](#backfilling-概念)
3. [使用方法](#使用方法)
4. [實際場景](#實際場景)
5. [最佳實踐](#最佳實踐)
6. [故障排查](#故障排查)

---

## Feature Versioning 概念

### 什麼是 Feature Versioning？

**Feature Versioning** 係為 feature transformations 建立唔同版本，確保：
- 舊 models 繼續使用佢哋訓練時嘅 feature definitions
- 新 feature 改動唔會影響 production models
- 可以同時運行多個 feature versions 做 A/B testing
- 可以 reproduce 歷史 training datasets

### 點解需要？

#### 問題 1: Production Model Stability
```
情境：你有個 fraud detection model 喺 production 運行緊

Version 1 (原本):
txn_count_1h = COUNT(all transactions in last 1 hour)

Version 2 (改良):
txn_count_1h = COUNT(approved transactions in last 1 hour)  // exclude declined

問題：如果直接改，production model 會收到唔同嘅 features
→ Model accuracy 會急跌
→ False positives/negatives 增加
→ Business impact 嚴重
```

#### 問題 2: A/B Testing
```
你想測試新 feature definition 係咪真係好啲：
- Model A (v1 features): baseline performance
- Model B (v2 features): test performance

需要兩個版本並存，先可以做有效比較
```

#### 問題 3: Reproducibility
```
6 個月後你想 reproduce 舊 model：
- 但 feature definitions 已經改過 3 次
- 無法重現當時嘅 training data
- 無法 debug model 問題
```

### 實現方式

#### 方法 1: Feature Group Versioning (推薦)
```
rt_card_features_v1  ← Production models
rt_card_features_v2  ← Testing new features
rt_card_features_v3  ← Experimental
```

**優點**:
- 完全獨立，互不影響
- 可以有唔同 schema
- Easy rollback

**缺點**:
- 需要 maintain 多個 feature groups
- Storage cost 較高

#### 方法 2: Schema-based Versioning (本 repo 實現)
```sql
-- 同一個 feature group，加 feature_version column
card_id | event_time | txn_count_1h | feature_version
--------|------------|--------------|----------------
card_01 | 1234567890 | 5            | v1
card_01 | 1234567895 | 3            | v2
```

**優點**:
- 單一 feature group，easier to manage
- 可以 query 特定 version
- 節省 storage

**缺點**:
- Schema 必須 compatible
- Query 時要 filter by version

---

## Backfilling 概念

### 什麼是 Backfilling？

**Backfilling** 係指重新處理歷史數據，regenerate features for a specific time range。

### 何時需要 Backfill？

#### 1. Feature Definition 改變
```
舊 feature: txn_count_1h (exclude declined)
新 feature: txn_count_1h (include all)

需要 backfill 過去 30 天數據，用新 definition 重新計算
```

#### 2. Bug Fix
```
發現 feature 計算有 bug：
- merchant_count_24h 計錯咗 window size (用咗 12h)
- 需要 backfill 修正所有受影響嘅數據
```

#### 3. Data Quality Issue
```
上游 data source 修正咗歷史數據：
- Bronze layer 已經 corrected
- 需要 backfill Silver → Gold → Feature Store
```

#### 4. New Model Training
```
需要訓練新 model：
- 需要過去 1 年嘅 training data
- 但 feature store 只有 30 天數據
- 需要 backfill 歷史數據
```

---

## 使用方法

### 前置條件

1. Bronze layer 數據已存在
2. EMR Serverless application 已建立
3. Feature Store feature group 已註冊
4. 有足夠 IAM permissions

### 方法 1: 使用 Helper Script (推薦)

#### 基本用法

```bash
# 安裝 dependencies
pip install boto3

# Backfill 單一日期
python scripts/run_backfill.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-01 \
  --state-machine-arn arn:aws:states:ap-southeast-1:ACCOUNT:stateMachine:backfill-pipeline \
  --bucket your-datalake-bucket \
  --code-bucket your-code-bucket \
  --emr-app-id YOUR_EMR_APP_ID \
  --emr-job-role arn:aws:iam::ACCOUNT:role/EMRJobRole \
  --feature-group rt_card_features_v1 \
  --glue-crawler gold-crawler
```

#### Backfill 一週數據

```bash
python scripts/run_backfill.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-07 \
  --chunk-size-days 1 \
  --state-machine-arn $SFN_ARN \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE \
  --feature-group rt_card_features_v1
```

#### Backfill with Feature Version

```bash
# Backfill 用 v2 feature definitions
python scripts/run_backfill.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-07 \
  --feature-version v2 \
  --state-machine-arn $SFN_ARN \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE \
  --feature-group rt_card_features_v2
```

#### Overwrite Mode (小心使用)

```bash
# Overwrite 現有數據
python scripts/run_backfill.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-07 \
  --overwrite \
  --state-machine-arn $SFN_ARN \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE
```

#### Dry Run (測試用)

```bash
# 測試 backfill logic 但唔寫數據
python scripts/run_backfill.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-07 \
  --dry-run \
  --state-machine-arn $SFN_ARN \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE
```

#### Direct EMR Execution (跳過 Step Functions)

```bash
python scripts/run_backfill.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-07 \
  --direct-emr \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE
```

### 方法 2: 直接提交 Spark Job

```bash
aws emr-serverless start-job-run \
  --application-id YOUR_EMR_APP_ID \
  --execution-role-arn YOUR_ROLE_ARN \
  --job-driver '{
    "sparkSubmit": {
      "entryPoint": "s3://your-code-bucket/spark_jobs/backfill_features.py",
      "entryPointArguments": [
        "--bucket", "your-datalake-bucket",
        "--bronze-prefix", "bronze/streaming",
        "--silver-prefix", "silver",
        "--gold-prefix", "gold",
        "--feature-group", "rt_card_features_v1",
        "--start-date", "2025-10-01",
        "--end-date", "2025-10-07",
        "--feature-version", "v1",
        "--chunk-size-days", "1"
      ],
      "sparkSubmitParameters": "--conf spark.executor.cores=2 --conf spark.executor.memory=8g"
    }
  }'
```

### 方法 3: 透過 Step Functions

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT:stateMachine:backfill-pipeline \
  --input '{
    "bucket": "your-datalake-bucket",
    "codeBucket": "your-code-bucket",
    "startDate": "2025-10-01",
    "endDate": "2025-10-07",
    "featureVersion": "v1",
    "chunkSizeDays": 1,
    "overwrite": false,
    "dryRun": false,
    "featureGroup": "rt_card_features_v1",
    "emr": {
      "appId": "YOUR_EMR_APP_ID",
      "jobRole": "arn:aws:iam::ACCOUNT:role/EMRJobRole"
    },
    "glue": {
      "crawlerName": "gold-crawler"
    }
  }'
```

---

## 實際場景

### Scenario 1: Feature Bug Fix

**問題**: 發現 `txn_count_1h` 計算錯誤，少咗某啲 transactions

**解決方案**:
```bash
# Step 1: Fix code in spark_jobs/silver_and_gold.py
# (修正 feature calculation logic)

# Step 2: Backfill last 7 days
python scripts/run_backfill.py \
  --start-date 2025-10-13 \
  --end-date 2025-10-20 \
  --feature-version v1 \
  --overwrite \
  --state-machine-arn $SFN_ARN \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE

# Step 3: Verify results
aws athena start-query-execution \
  --query-string "SELECT COUNT(*), feature_version, DATE(FROM_UNIXTIME(event_time)) as dt 
                  FROM gold.card_features 
                  WHERE dt BETWEEN '2025-10-13' AND '2025-10-20' 
                  GROUP BY feature_version, DATE(FROM_UNIXTIME(event_time))"
```

### Scenario 2: New Feature Version Testing

**問題**: 想測試新 feature definitions 但唔想影響 production

**解決方案**:
```bash
# Step 1: Update transformation logic with version check
# In spark_jobs/silver_and_gold.py or backfill_features.py:
if feature_version == "v2":
    # New feature logic
    gold_df = gold_df.withColumn("txn_count_1h", 
                                  count_approved_only(...))
else:
    # Original logic
    gold_df = gold_df.withColumn("txn_count_1h", 
                                  count_all(...))

# Step 2: Create v2 feature group (optional)
# If using separate feature groups

# Step 3: Backfill with v2
python scripts/run_backfill.py \
  --start-date 2025-09-01 \
  --end-date 2025-09-30 \
  --feature-version v2 \
  --state-machine-arn $SFN_ARN \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE \
  --feature-group rt_card_features_v2

# Step 4: Train model with v2 features
# Step 5: Compare v1 vs v2 model performance
# Step 6: Promote v2 to production if better
```

### Scenario 3: Large Historical Backfill

**問題**: 需要 backfill 1 年歷史數據訓練新 model

**解決方案**:
```bash
# Step 1: Estimate cost first
python scripts/run_backfill.py \
  --start-date 2024-10-01 \
  --end-date 2025-10-01 \
  --chunk-size-days 7 \
  --dry-run \
  --state-machine-arn $SFN_ARN \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE

# Step 2: Run backfill in larger chunks for cost efficiency
python scripts/run_backfill.py \
  --start-date 2024-10-01 \
  --end-date 2025-10-01 \
  --chunk-size-days 7 \
  --state-machine-arn $SFN_ARN \
  --bucket $BUCKET \
  --code-bucket $CODE_BUCKET \
  --emr-app-id $EMR_APP \
  --emr-job-role $EMR_ROLE

# Step 3: Monitor progress via CloudWatch
# Step 4: Verify completeness
```

---

## 最佳實踐

### 1. Chunk Size Selection

| Date Range | Recommended Chunk Size | Reason |
|-----------|------------------------|--------|
| 1-7 days | 1 day | Fast iteration, easy debugging |
| 1-3 months | 3-7 days | Balance cost and reliability |
| 3-12 months | 7-14 days | Cost optimization |

### 2. Feature Versioning Strategy

```
v1: Production stable version
v2: Testing/staging version
v3: Experimental version
```

**命名規範**:
- `v{major}`: Breaking changes (schema change, logic 完全唔同)
- `v{major}.{minor}`: Non-breaking changes (optimization, bug fix)

**Example**:
- `v1.0`: Initial production
- `v1.1`: Bug fix (compatible)
- `v2.0`: New feature definitions (incompatible)

### 3. Data Validation

```python
# 喺 backfill 前後 validate data
# Before backfill
SELECT COUNT(*), MIN(event_time), MAX(event_time)
FROM gold.card_features
WHERE dt = '2025-10-01';

# After backfill
SELECT COUNT(*), MIN(event_time), MAX(event_time), feature_version
FROM gold.card_features
WHERE dt = '2025-10-01'
GROUP BY feature_version;

# Compare counts
# Verify no duplicates
SELECT card_id, event_id, COUNT(*)
FROM gold.card_features
WHERE dt = '2025-10-01'
GROUP BY card_id, event_id
HAVING COUNT(*) > 1;
```

### 4. Overwrite 使用指引

**何時使用 `--overwrite`**:
- ✅ Bug fix (需要替換錯誤數據)
- ✅ Data quality issue (上游數據已修正)
- ✅ 測試環境

**何時避免 `--overwrite`**:
- ❌ Production backfill (除非絕對必要)
- ❌ 唔確定數據 correctness
- ❌ 多個 feature versions 並存時

**Safer Alternative**:
```bash
# 唔用 overwrite，而係用 feature_version 區分
--feature-version v1_corrected
```

### 5. Cost Optimization

#### Tip 1: 用 Spot Instances (如果 EMR Serverless 支援)
```bash
# Configure EMR Serverless with spot capacity
# (Check AWS documentation for latest capabilities)
```

#### Tip 2: Adjust Spark Configuration
```bash
# For small data volume (< 1GB per day)
--conf spark.executor.cores=1
--conf spark.executor.memory=4g
--conf spark.executor.instances=2

# For large data volume (> 10GB per day)
--conf spark.executor.cores=4
--conf spark.executor.memory=16g
--conf spark.executor.instances=8
```

#### Tip 3: Partition Pruning
```python
# 確保 backfill script 只 read 需要嘅 partitions
bronze_df = spark.read.json(f"{bronze_path}/dt={target_date}/*.json.gz")
# Instead of reading everything
```

### 6. Monitoring

```bash
# CloudWatch Metrics to monitor
- BackfillPipelineSuccess (custom metric)
- EMR Serverless job duration
- S3 read/write bytes
- Feature Store ingestion rate

# Set up alarms
aws cloudwatch put-metric-alarm \
  --alarm-name backfill-job-failed \
  --metric-name BackfillPipelineSuccess \
  --namespace P1Unified \
  --statistic Sum \
  --period 3600 \
  --threshold 0 \
  --comparison-operator LessThanThreshold
```

---

## 故障排查

### Issue 1: Backfill Job Failed

**症狀**: EMR Serverless job 失敗

**Debug Steps**:
```bash
# 1. Check job logs
aws emr-serverless get-job-run \
  --application-id YOUR_APP_ID \
  --job-run-id YOUR_JOB_RUN_ID

# 2. Check CloudWatch Logs
# Navigate to: /aws/emr-serverless/applications/{app-id}/jobs/{job-id}

# 3. Common causes
# - Insufficient memory (OOM)
# - Missing S3 data
# - IAM permission issues
# - Feature Store throttling
```

**Solutions**:
```bash
# Increase memory
--conf spark.executor.memory=16g
--conf spark.driver.memory=16g

# Reduce batch size
--chunk-size-days 1

# Check IAM permissions
aws iam get-role --role-name EMRJobRole
```

### Issue 2: Feature Store Ingestion Throttled

**症狀**: `ThrottlingException` 喺 batch_put_record

**Solutions**:
```python
# 1. Reduce batch size
batch_size = 50  # Instead of 100

# 2. Add retry logic with exponential backoff
import time
from botocore.exceptions import ClientError

max_retries = 3
for attempt in range(max_retries):
    try:
        client.batch_put_record(...)
        break
    except ClientError as e:
        if e.response['Error']['Code'] == 'ThrottlingException':
            time.sleep(2 ** attempt)
        else:
            raise

# 3. Request quota increase from AWS Support
```

### Issue 3: Duplicate Records

**症狀**: 同一個 event_id 出現多次

**Debug**:
```sql
SELECT card_id, event_id, COUNT(*)
FROM gold.card_features
WHERE dt = '2025-10-01'
GROUP BY card_id, event_id
HAVING COUNT(*) > 1;
```

**Causes**:
- 執行咗 backfill 兩次 without `--overwrite`
- Bronze data 本身有 duplicates

**Solutions**:
```bash
# Solution 1: Re-run with --overwrite
python scripts/run_backfill.py --overwrite ...

# Solution 2: Deduplicate manually
CREATE TABLE gold.card_features_deduped AS
SELECT DISTINCT *
FROM gold.card_features
WHERE dt = '2025-10-01';
```

### Issue 4: Missing Historical Data

**症狀**: Backfill 完成但某啲日期 missing data

**Debug**:
```sql
-- Check Bronze layer coverage
SELECT dt, COUNT(*)
FROM bronze.card_authorization
WHERE dt BETWEEN '2025-10-01' AND '2025-10-07'
GROUP BY dt
ORDER BY dt;

-- Check Gold layer
SELECT dt, COUNT(*)
FROM gold.card_features
WHERE dt BETWEEN '2025-10-01' AND '2025-10-07'
GROUP BY dt
ORDER BY dt;
```

**Solutions**:
- 確認 Bronze layer 數據存在
- 檢查 date range 係咪正確
- Re-run backfill for missing dates

---

## Performance Tuning

### Spark Configuration 建議

```python
# Small backfill (< 1 week)
{
  "spark.executor.cores": 2,
  "spark.executor.memory": "8g",
  "spark.driver.cores": 2,
  "spark.driver.memory": "8g",
  "spark.executor.instances": 2,
  "spark.sql.shuffle.partitions": 50
}

# Medium backfill (1-4 weeks)
{
  "spark.executor.cores": 2,
  "spark.executor.memory": "8g",
  "spark.driver.cores": 2,
  "spark.driver.memory": "8g",
  "spark.executor.instances": 4,
  "spark.sql.shuffle.partitions": 100
}

# Large backfill (> 1 month)
{
  "spark.executor.cores": 4,
  "spark.executor.memory": "16g",
  "spark.driver.cores": 4,
  "spark.driver.memory": "16g",
  "spark.executor.instances": 8,
  "spark.sql.shuffle.partitions": 200
}
```

---

## 參考資料

- [AWS EMR Serverless Documentation](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/)
- [SageMaker Feature Store Best Practices](https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store-best-practices.html)
- [Spark Performance Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)

---

**Last Updated**: 2025-10-20  
**Author**: Patrick Cheung
