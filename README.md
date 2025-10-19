# AWS Batch Realtime Medallion ML Feature Platform Pipeline

## 概述

呢個係一個基於 AWS 嘅 **Serverless Realtime Medallion Architecture** 同 **ML Feature Platform**，用於處理實時卡交易數據、特徵工程同機器學習數據集建立。

### 架構特點

- **Region**: `ap-southeast-1` (Singapore)
- **數據層級**: Bronze → Silver → Gold (Medallion Architecture)
- **實時處理**: Kinesis + Firehose + EMR Serverless (每 10 分鐘)
- **特徵平台**: SageMaker Feature Store (Online + Offline)
- **批次處理**: 每日輸出 training/ 同 inference/ datasets
- **編排**: Step Functions single state machine
- **IaC**: Terraform modules
- **CI/CD**: GitHub Actions with OIDC

---

## 架構圖

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Kinesis   │────▶│   Firehose   │────▶│ S3 Bronze/   │
│ Data Stream │     │              │     │  streaming   │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                    ┌────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  EventBridge         │
         │  (*/10m & Daily)     │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Step Functions      │
         │  stream_pipeline     │
         └──────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌──────────────┐      ┌──────────────────┐
│ EMR          │      │ EMR              │
│ Serverless:  │      │ Serverless:      │
│ silver_and_  │      │ build_datasets   │
│ gold.py      │      │ .py              │
└──────┬───────┘      └─────────┬────────┘
       │                        │
       ▼                        ▼
┌─────────────┐         ┌──────────────┐
│ S3 Silver/  │         │ S3 Gold/     │
│ Gold/       │         │ training/    │
└─────────────┘         │ inference/   │
       │                └──────────────┘
       │
       ▼
┌──────────────────────┐
│ SageMaker Feature    │
│ Store (Online +      │
│ Offline)             │
└──────────────────────┘
```

---

## 目錄結構

```
.
├── infra/terraform/            # Terraform IaC
│   ├── main.tf
│   ├── providers.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── s3_datalake/
│       ├── kinesis_firehose/
│       ├── emr_serverless/
│       ├── glue/
│       ├── sagemaker_featurestore/
│       ├── step_functions/
│       ├── eventbridge/
│       └── cloudwatch/
├── state_machines/
│   └── stream_pipeline.asl.json
├── spark_jobs/
│   ├── silver_and_gold.py
│   └── build_datasets.py
├── feature_store/
│   ├── register_feature_groups.py
│   └── ingest_features.py
├── scripts/
│   └── generate_synthetic_batch.py
├── .github/workflows/
│   ├── deploy.yml
│   └── destroy.yml
└── README.md
```

---

## 數據模型

### Bronze Layer
- **Path**: `s3://bucket/bronze/streaming/card_authorization/ingest_dt=YYYY/MM/DD/HH/mm/*.json.gz`
- **Schema**:
  - `event_id` (string)
  - `card_id` (string)
  - `ts` (timestamp)
  - `merchant_id` (string)
  - `amount` (float)
  - `currency` (string)
  - `country` (string)
  - `pos_mode` (string)

### Silver Layer
- **Path**: `s3://bucket/silver/card_transactions/dt=YYYY-MM-DD/*.parquet`
- **描述**: 清洗後嘅數據，去重、驗證

### Gold Layer
- **Path**: `s3://bucket/gold/card_features/dt=YYYY-MM-DD/*.parquet`
- **Features**:
  - `txn_count_1h`: 過去 1 小時交易次數
  - `txn_amount_1h`: 過去 1 小時交易金額
  - `merchant_count_24h`: 過去 24 小時唔同商戶數量
  - `avg_amount_7d`: 過去 7 日平均交易金額

### Training/Inference Datasets
- **Training**: `s3://bucket/gold/training/dt=YYYY-MM-DD/{train,validation}/*.parquet`
- **Inference**: `s3://bucket/gold/inference/dt=YYYY-MM-DD/*.parquet`

---

## 部署指南

### 前置要求

1. **AWS Account** with appropriate permissions
2. **Terraform** >= 1.5.0
3. **AWS CLI** configured
4. **GitHub** repository with OIDC configured

### 環境變數 / Secrets

在 GitHub repository 設定以下 secrets：

- `ASSUME_ROLE_ARN`: OIDC role ARN for GitHub Actions
- `TF_BACKEND_BUCKET`: S3 bucket for Terraform state
- `TF_BACKEND_DDB_TABLE`: DynamoDB table for state locking
- `AWS_ACCOUNT_ID`: Your AWS account ID

### 部署步驟

#### 1. 建立 Terraform Backend

```bash
# 建立 S3 bucket for Terraform state
aws s3 mb s3://your-terraform-state-bucket --region ap-southeast-1

# 建立 DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --region ap-southeast-1
```

#### 2. 配置 OIDC for GitHub Actions

參考 [AWS documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) 設定 GitHub OIDC provider。

#### 3. 本地部署（測試）

```bash
cd infra/terraform

# Initialize
terraform init \
  -backend-config="bucket=your-terraform-state-bucket" \
  -backend-config="key=aws-batch-realtime-medallion/terraform.tfstate" \
  -backend-config="region=ap-southeast-1" \
  -backend-config="dynamodb_table=terraform-state-lock"

# Plan
terraform plan

# Apply
terraform apply
```

#### 4. GitHub Actions 部署

Push to `main` branch 或手動觸發 `deploy.yml` workflow。

---

## 使用方法

### 生成測試數據

```bash
# 生成一次性批次數據
python scripts/generate_synthetic_batch.py \
  --num-transactions 1000 \
  --kinesis-stream your-stream-name \
  --region ap-southeast-1

# 連續生成數據 (10 TPS)
python scripts/generate_synthetic_batch.py \
  --continuous \
  --rate 10 \
  --kinesis-stream your-stream-name \
  --region ap-southeast-1
```

### 手動觸發 Pipeline

```bash
# Stream mode (processing)
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:ap-southeast-1:ACCOUNT:stateMachine:stream-pipeline \
  --input file://stream_input.json

# Daily mode (datasets)
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:ap-southeast-1:ACCOUNT:stateMachine:stream-pipeline \
  --input file://daily_input.json
```

### 查詢 Feature Store

```python
from feature_store.ingest_features import FeatureStoreIngester

ingester = FeatureStoreIngester(feature_group_name="rt_card_features_v1")
record = ingester.get_record("card_001")
print(record)
```

---

## Monitoring

### CloudWatch Dashboard

訪問: AWS Console → CloudWatch → Dashboards → `{project}-{env}-dashboard`

包含以下 metrics：
- Step Functions 執行狀態
- EMR Serverless job 成功率
- Kinesis Firehose delivery 成功率
- Custom pipeline metrics

### Alarms

- **SFN Execution Failed**: Step Functions 執行失敗
- **Firehose Delivery Failed**: Firehose delivery 成功率低於 95%

---

## 成本估算

以 **dev** 環境為例（每日約 1M events）：

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| Kinesis Data Stream | 1 shard, 24/7 | $11/month |
| Kinesis Firehose | 1M records | $5/month |
| S3 Storage | 100 GB | $2.3/month |
| EMR Serverless | 144 runs/day, 5min each | $20/month |
| Step Functions | 144 executions/day | $0.03/month |
| SageMaker Feature Store | 1M writes, 100K reads | $10/month |
| **Total** | | **~$50/month** |

**建議**:
- 使用 S3 Lifecycle policies (30 days retention)
- EMR Serverless auto-stop (15 min idle)
- Kinesis on-demand mode for variable workloads

---

## Troubleshooting

### EMR Job 失敗

1. 檢查 CloudWatch Logs: `/aws/emr-serverless/applications/{app-id}/jobs/{job-id}`
2. 驗證 S3 permissions
3. 檢查 Spark job code syntax

### Feature Store Upsert 失敗

1. 確保 Feature Group 已建立並處於 `Created` 狀態
2. 檢查 IAM role permissions (`sagemaker-featurestore-runtime:BatchPutRecord`)
3. 驗證 feature definitions 同 data schema 一致

### Step Functions 超時

1. 增加 EMR Serverless capacity
2. 調整 `WaitSilver` / `WaitDaily` 嘅 `Seconds` 值
3. 檢查 EMR job 係咪卡喺某個 stage

---

## Development

### 本地測試 Spark Jobs

```bash
# 使用 local Spark
spark-submit \
  --master local[*] \
  spark_jobs/silver_and_gold.py \
  --bucket test-bucket \
  --bronze-prefix bronze/streaming \
  --silver-prefix silver \
  --gold-prefix gold \
  --feature-group rt_card_features_v1 \
  --window-end-ts 2025-10-19T12:00:00Z
```

---

## 參考資料

- [AWS EMR Serverless](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/)
- [SageMaker Feature Store](https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store.html)
- [Step Functions](https://docs.aws.amazon.com/step-functions/)

---

## License

MIT License - Patrick Cheung

---

## Roadmap

- [ ] M0: Infrastructure setup
- [ ] M1: Streaming pipeline (P1 Unified)
- [ ] M2: Daily datasets pipeline
- [ ] M3: Documentation & CI/CD integration
- [ ] Future: Model training integration (out-of-scope for this repo)

---

**Author**: Patrick Cheung  
**Last Updated**: 2025-10-19
