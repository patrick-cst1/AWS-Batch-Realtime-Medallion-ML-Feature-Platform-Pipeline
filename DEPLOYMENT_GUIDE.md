# 1st-time Deployment Guide (Cost-Optimized)

本指南以最少步驟、最低成本為目標，帶你完成首次部署。預設 Region 為 `ap-southeast-1`。

---

## 1. Prerequisites
- 已安裝並登入 `AWS CLI`（`aws configure`）。
- GitHub Repo 已可用（此 Repo）。
- 不需要在本機安裝 Terraform（GitHub Actions 會安裝）。

---

## 2. One-off 基礎設置

### 2.1 建立 Terraform Backend（S3 + DynamoDB）
- S3（存 Terraform state）：
```powershell
aws s3 mb s3://acme-mlfeature-tfstate-dev --region ap-southeast-1
```
- DynamoDB（state lock，建議 On-Demand 最慳錢）：
```powershell
aws dynamodb create-table --table-name acme-mlfeature-tflock-dev --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region ap-southeast-1
```

### 2.2 設定 GitHub OIDC + IAM Role（讓 Actions Assume Role）
- 檢查/建立 GitHub OIDC Provider：
```powershell
aws iam list-open-id-connect-providers
aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```
- 建立供 GitHub Actions 使用的 IAM Role（替換佔位）：
```powershell
aws iam create-role --role-name GithubActionsDeployRole --assume-role-policy-document '{ "Version": "2012-10-17", "Statement": [ { "Effect": "Allow", "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" }, "Action": "sts:AssumeRoleWithWebIdentity", "Condition": { "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" }, "StringLike": { "token.actions.githubusercontent.com:sub": "repo:<GH_ORG>/<GH_REPO>:*" } } } ] }'
aws iam attach-role-policy --role-name GithubActionsDeployRole --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam get-role --role-name GithubActionsDeployRole --query 'Role.Arn' --output text
```
> 注意：thumbprint 請以 AWS 官方文檔核實最新值；`AdministratorAccess` 方便首次部署，穩定後請收窄到最小權限。

### 2.3 設定 GitHub Secrets
Repo → Settings → Secrets and variables → Actions：
- `ASSUME_ROLE_ARN`：上一步輸出的 Role ARN
- `TF_BACKEND_BUCKET`：`acme-mlfeature-tfstate-dev`
- `TF_BACKEND_DDB_TABLE`：`acme-mlfeature-tflock-dev`

---

## 3. Cost-friendly 設定（已預置）
- Kinesis：`ON_DEMAND`（低流量更慳錢）。
- S3：`SSE-S3 (AES256)`（移除 KMS 固定費）。
- EMR Serverless 初始資源：Driver/Executor 各 `1 vCPU / 4 GB`。
- `infra/terraform/terraform.tfvars`：
```hcl
stream_pipeline_schedule_minutes = 60
s3_lifecycle_days = 7
```
> Demo 期建議先在 AWS Console Disable `EventBridge` 規則（stream/daily），需要時才手動觸發 `Step Functions`，可將固定成本降至近乎 0。

---

## 4. 部署（GitHub Actions）
- 直接 push 到 `main` 分支，會觸發 `.github/workflows/deploy.yml`：
  - Terraform `init/plan/apply` 會建立整套基建。
  - 自動同步 `spark_jobs/`、`feature_store/` 到 S3 code bucket。
  - `terraform apply -refresh-only` 更新 Step Functions。
- 可於 Actions 手動 `Run workflow`（注意：Workflow 內的 Smoke Test 目前示例 `jobRole` 為空，如需使用，請將其改為 Terraform Output 之 EMR Job Role ARN）。

---

## 5. 驗證
- Terraform Outputs（在 Actions 日誌或本地 `terraform output`）：
  - `code_bucket_name`、`datalake_bucket_name`、`emr_application_id`、`step_function_arn`。
- 產生測試數據（可選）：
```powershell
pip install -r requirements.txt
python scripts/generate_synthetic_batch.py --num-transactions 200 --kinesis-stream <your-stream-name> --region ap-southeast-1
```
- 手動觸發 Step Functions（Stream 模式）：
```powershell
$SFN_ARN = '<STEP_FUNCTION_ARN>'
$APP_ID = '<EMR_APPLICATION_ID>'
$DATA_BUCKET = '<DATALAKE_BUCKET>'
$CODE_BUCKET = '<CODE_BUCKET>'
$NOW = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
aws stepfunctions start-execution --state-machine-arn $SFN_ARN --input "{\"mode\":\"stream\",\"now\":\"$NOW\",\"bucket\":\"$DATA_BUCKET\",\"codeBucket\":\"$CODE_BUCKET\",\"bronzePrefix\":\"bronze/streaming\",\"silverPrefix\":\"silver\",\"goldPrefix\":\"gold\",\"featureGroup\":\"rt_card_features_v1\",\"emr\":{\"appId\":\"$APP_ID\",\"jobRole\":\"<EMR_JOB_ROLE_ARN>\"}}"
```
- 觀察：
  - CloudWatch Logs（EMR Serverless / Step Functions / Firehose）
  - CloudWatch Dashboard：`{project}-{env}-dashboard`

---

## 6. 銷毀（避免後續費用）
- 推薦使用工作流 `.github/workflows/destroy.yml`：
  - 在 Actions → `Destroy Infrastructure` → `Run workflow` → `confirm` 輸入 `destroy`。
  - 注意：S3 bucket 非空時，Terraform 可能無法自動刪除；請先清空或手動刪除 bucket。
- 可選（自動清桶）：把 `infra/terraform/modules/s3_datalake/*` 的 S3 bucket 資源加入 `force_destroy = true`（生產環境慎用）。

---

## 7. 常見問題（FAQ）
- 是否需要本機安裝 Terraform？不需要（Actions 會安裝）。
- OIDC Provider 是否必需？是（若使用 Actions Assume Role）。
- 估計成本？Demo 期如停用排程、低流量：每月常見成本多為 S3/Logs 幾蚊級；有手動 EMR Job 時才產生成本。
