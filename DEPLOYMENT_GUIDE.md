# 1st-time Deployment Guide (Cost-Optimized)

This guide focuses on the minimum steps and lowest cost to complete your first deployment. The default region is `ap-southeast-1`.

---

## 1. Prerequisites
- AWS CLI installed and logged in (`aws configure`).
- GitHub repository available (this repository).
- No need to install Terraform locally (GitHub Actions will install it).

---

## 2. One-off Basic Setup

### 2.1 Create Terraform Backend (S3 + DynamoDB)
- S3 (stores Terraform state):
```powershell
aws s3 mb s3://acme-mlfeature-tfstate-dev --region ap-southeast-1
```
- DynamoDB (state lock, recommended On-Demand for lowest cost):
```powershell
aws dynamodb create-table --table-name acme-mlfeature-tflock-dev --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region ap-southeast-1
```

### 2.2 Configure GitHub OIDC + IAM Role (Allow Actions to Assume Role)
- Check/create GitHub OIDC Provider:
```powershell
aws iam list-open-id-connect-providers
aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```
- Create IAM Role for GitHub Actions (replace placeholders):
```powershell
aws iam create-role --role-name GithubActionsDeployRole --assume-role-policy-document '{ "Version": "2012-10-17", "Statement": [ { "Effect": "Allow", "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" }, "Action": "sts:AssumeRoleWithWebIdentity", "Condition": { "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" }, "StringLike": { "token.actions.githubusercontent.com:sub": "repo:<GH_ORG>/<GH_REPO>:*" } } } ] }'
aws iam attach-role-policy --role-name GithubActionsDeployRole --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam get-role --role-name GithubActionsDeployRole --query 'Role.Arn' --output text
```
> Note: Verify the latest thumbprint from AWS official documentation; `AdministratorAccess` is convenient for initial deployment, but narrow to minimum permissions when stable.

### 2.3 Configure GitHub Secrets
Repository → Settings → Secrets and variables → Actions:
- `ASSUME_ROLE_ARN`: Role ARN from step above
- `TF_BACKEND_BUCKET`: `acme-mlfeature-tfstate-dev`
- `TF_BACKEND_DDB_TABLE`: `acme-mlfeature-tflock-dev`

---

## 3. Cost-friendly Configuration (Pre-configured)
- Kinesis: `ON_DEMAND` (cheaper for low traffic).
- S3: `SSE-S3 (AES256)` (removes KMS fixed cost).
- EMR Serverless initial resources: Driver/Executor each `1 vCPU / 4 GB`.
- `infra/terraform/terraform.tfvars`:
```hcl
stream_pipeline_schedule_minutes = 60
s3_lifecycle_days = 7
```
> For demo period, consider disabling `EventBridge` rules (stream/daily) in AWS Console when needed to manually trigger `Step Functions`, which can reduce fixed costs to near zero.

---

## 4. Deployment (GitHub Actions)
- Directly push to `main` branch to trigger `.github/workflows/deploy.yml`:
  - Terraform `init/plan/apply` will create the entire infrastructure.
  - Automatically sync `spark_jobs/`, `feature_store/` to S3 code bucket.
  - `terraform apply -refresh-only` updates Step Functions.
- Manual `Run workflow` in Actions (note: Smoke Test in workflow currently has empty `jobRole`, change to Terraform Output EMR Job Role ARN if needed).

---

## 5. Verification
- Terraform Outputs (in Actions logs or local `terraform output`):
  - `code_bucket_name`, `datalake_bucket_name`, `emr_application_id`, `step_function_arn`.
- Generate test data (optional):
```powershell
pip install -r requirements.txt
python scripts/generate_synthetic_batch.py --num-transactions 200 --kinesis-stream <your-stream-name> --region ap-southeast-1
```
- Manually trigger Step Functions (Stream mode):
```powershell
$SFN_ARN = '<STEP_FUNCTION_ARN>'
$APP_ID = '<EMR_APPLICATION_ID>'
$DATA_BUCKET = '<DATALAKE_BUCKET>'
$CODE_BUCKET = '<CODE_BUCKET>'
$NOW = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
aws stepfunctions start-execution --state-machine-arn $SFN_ARN --input "{\"mode\":\"stream\",\"now\":\"$NOW\",\"bucket\":\"$DATA_BUCKET\",\"codeBucket\":\"$CODE_BUCKET\",\"bronzePrefix\":\"bronze/streaming\",\"silverPrefix\":\"silver\",\"goldPrefix\":\"gold\",\"featureGroup\":\"rt_card_features_v1\",\"emr\":{\"appId\":\"$APP_ID\",\"jobRole\":\"<EMR_JOB_ROLE_ARN>\"}}"
```
- Observe:
  - CloudWatch Logs (EMR Serverless / Step Functions / Firehose)
  - CloudWatch Dashboard: `{project}-{env}-dashboard`

---

## 6. Destruction (Avoid Ongoing Costs)
- Recommended to use workflow `.github/workflows/destroy.yml`:
  - In Actions → `Destroy Infrastructure` → `Run workflow` → Input `destroy` for confirmation.
  - Note: S3 bucket non-empty may prevent Terraform auto-deletion; empty or manually delete bucket first.
- Optional (auto bucket deletion): Add `force_destroy = true` to S3 bucket resource in `infra/terraform/modules/s3_datalake/*` (not recommended for production).

---

## 7. Common Issues (FAQ)
- Do I need to install Terraform locally? No (Actions will install it).
- Is OIDC Provider required? Yes (if using Actions Assume Role).
- Estimated cost? Demo period with disabled scheduling and low traffic: mostly S3/Logs a few cents per month; costs only when manual EMR Jobs run.

---
