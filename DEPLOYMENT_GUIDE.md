<div align="center">

# 🚀 First-Time Deployment Guide

**Cost-Optimized AWS Infrastructure Setup**

[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?style=flat-square&logo=terraform)](https://www.terraform.io/)
[![AWS](https://img.shields.io/badge/Cloud-AWS-FF9900?style=flat-square&logo=amazon-aws)](https://aws.amazon.com/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=flat-square&logo=github-actions&logoColor=white)](https://github.com/features/actions)

Default Region: `ap-southeast-1` (Singapore)

</div>

---

## 📋 Prerequisites

<table>
<tr>
<td width="33%">

### ✅ AWS CLI
```bash
aws configure
```
Installed and authenticated

</td>
<td width="33%">

### ✅ GitHub Repo
This repository  
cloned/forked

</td>
<td width="33%">

### ✅ Terraform
**Not required locally**  
GitHub Actions handles it

</td>
</tr>
</table>

---

## 🛠️ One-Time Basic Setup

### Step 1️⃣: Create Terraform Backend

<details open>
<summary><b>🪣 S3 Bucket (State Storage)</b></summary>

```powershell
aws s3 mb s3://acme-mlfeature-tfstate-dev --region ap-southeast-1
```

**Purpose**: Stores Terraform state files

</details>

<details open>
<summary><b>🔒 DynamoDB Table (State Locking)</b></summary>

```powershell
aws dynamodb create-table `
  --table-name acme-mlfeature-tflock-dev `
  --attribute-definitions AttributeName=LockID,AttributeType=S `
  --key-schema AttributeName=LockID,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST `
  --region ap-southeast-1
```

**Billing**: `PAY_PER_REQUEST` (lowest cost for infrequent access)

</details>

---

### Step 2️⃣: Configure GitHub OIDC + IAM Role

<details open>
<summary><b>🔍 Check/Create OIDC Provider</b></summary>

```powershell
# List existing providers
aws iam list-open-id-connect-providers

# Create if not exists
aws iam create-open-id-connect-provider `
  --url https://token.actions.githubusercontent.com `
  --client-id-list sts.amazonaws.com `
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

> ⚠️ **Note**: Verify thumbprint from [AWS official docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)

</details>

<details open>
<summary><b>👤 Create IAM Role for GitHub Actions</b></summary>

```powershell
# Create role (replace <ACCOUNT_ID>, <GH_ORG>, <GH_REPO>)
aws iam create-role `
  --role-name GithubActionsDeployRole `
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:<GH_ORG>/<GH_REPO>:*"
        }
      }
    }]
  }'

# Attach permissions
aws iam attach-role-policy `
  --role-name GithubActionsDeployRole `
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# Get Role ARN
aws iam get-role `
  --role-name GithubActionsDeployRole `
  --query 'Role.Arn' `
  --output text
```

> 🔐 **Security**: `AdministratorAccess` for initial setup. Narrow to least-privilege after stabilization.

</details>

---

### Step 3️⃣: Configure GitHub Secrets

<div align="center">

**Repository** → **Settings** → **Secrets and variables** → **Actions**

</div>

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `ASSUME_ROLE_ARN` | `arn:aws:iam::...` | Role ARN from previous step |
| `TF_BACKEND_BUCKET` | `acme-mlfeature-tfstate-dev` | S3 bucket for Terraform state |
| `TF_BACKEND_DDB_TABLE` | `acme-mlfeature-tflock-dev` | DynamoDB table for state locking |

---

## 💰 Cost-Friendly Configuration

> ✅ **Pre-configured** - No action needed!

<table>
<tr>
<td width="25%">

**🌊 Kinesis**  
`ON_DEMAND` mode  
Pay-per-use

</td>
<td width="25%">

**🪣 S3**  
`SSE-S3` encryption  
No KMS cost

</td>
<td width="25%">

**⚡ EMR Serverless**  
Minimal resources  
1 vCPU / 4 GB each

</td>
<td width="25%">

**📅 Scheduling**  
60-min intervals  
7-day retention

</td>
</tr>
</table>

### Configuration File

```hcl
# infra/terraform/terraform.tfvars
stream_pipeline_schedule_minutes = 60
s3_lifecycle_days = 7
```

### 💡 Pro Tip: Near-Zero Cost Demo

Disable EventBridge rules in AWS Console during development:
- Manual pipeline triggering only
- ~$0 fixed costs (pay only for test runs)

---

## 🚀 Deployment (GitHub Actions)

### Automatic Deployment

```mermaid
graph LR
    A[Push to main] --> B[GitHub Actions]
    B --> C[Terraform init/plan/apply]
    C --> D[Sync code to S3]
    D --> E[Update Step Functions]
    E --> F[✅ Infrastructure Ready]
    
    style A fill:#2088FF
    style F fill:#28a745
```

**Trigger**: Push to `main` branch → `.github/workflows/deploy.yml`

### Manual Deployment

**Actions** → **Run workflow** → Select branch → **Run**

> ⚠️ **Note**: Smoke Test requires EMR Job Role ARN from Terraform outputs

---

## ✅ Verification

### 1️⃣ Check Terraform Outputs

<details>
<summary><b>📊 View Outputs</b></summary>

In **GitHub Actions logs** or locally:

```powershell
terraform output
```

**Expected Outputs**:
- `code_bucket_name`
- `datalake_bucket_name`
- `emr_application_id`
- `step_function_arn`

</details>

### 2️⃣ Generate Test Data (Optional)

```powershell
pip install -r requirements.txt

python scripts/generate_synthetic_batch.py `
  --num-transactions 200 `
  --kinesis-stream <your-stream-name> `
  --region ap-southeast-1
```

### 3️⃣ Trigger Step Functions

```powershell
# Set variables from Terraform outputs
$SFN_ARN = '<STEP_FUNCTION_ARN>'
$APP_ID = '<EMR_APPLICATION_ID>'
$DATA_BUCKET = '<DATALAKE_BUCKET>'
$CODE_BUCKET = '<CODE_BUCKET>'
$EMR_JOB_ROLE = '<EMR_JOB_ROLE_ARN>'
$NOW = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# Execute pipeline
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
  }"
```

### 4️⃣ Monitor Execution

| Resource | Access Path |
|----------|-------------|
| 📊 **CloudWatch Logs** | `/aws/emr-serverless/`, `/aws/states/` |
| 📈 **Dashboard** | CloudWatch → `{project}-{env}-dashboard` |
| 🔄 **Step Functions** | AWS Console → Step Functions → Executions |

---

## 🗑️ Destruction (Cleanup)

### Recommended: GitHub Actions Workflow

1. **Actions** → **Destroy Infrastructure**
2. **Run workflow**
3. Input `destroy` for confirmation
4. ✅ Confirm execution

> ⚠️ **Important**: Empty S3 buckets first if Terraform deletion fails

### Optional: Auto-Delete S3 Buckets

```hcl
# In infra/terraform/modules/s3_datalake/main.tf
resource "aws_s3_bucket" "..." {
  force_destroy = true  # ⚠️ Use with caution!
}
```

**Not recommended for production environments**

---

## ❓ FAQ

<details>
<summary><b>Q: Do I need Terraform installed locally?</b></summary>

**A**: No! GitHub Actions installs and runs Terraform automatically.

</details>

<details>
<summary><b>Q: Is OIDC Provider required?</b></summary>

**A**: Yes, if using GitHub Actions with AWS. It provides secure, temporary credentials without storing AWS keys in GitHub Secrets.

</details>

<details>
<summary><b>Q: What's the estimated cost for demo/dev?</b></summary>

**A**: With disabled scheduling and low traffic:
- **Fixed costs**: ~$0-5/month (S3, CloudWatch Logs)
- **Variable costs**: Only when manually triggering pipelines
- **Typical dev**: $10-20/month with occasional testing

</details>

<details>
<summary><b>Q: How do I reduce costs further?</b></summary>

**A**: 
1. Disable EventBridge rules (manual triggering only)
2. Enable S3 lifecycle policies (auto-delete old data)
3. Use EMR Serverless pre-initialized capacity sparingly
4. Delete resources when not in use

</details>

---

<div align="center">

**🎉 Deployment Complete!**

Next: [E2E Testing Guide](E2E_TESTING_GUIDE.md) for testing your pipeline

---

**Need Help?** Open an issue on GitHub

</div>

<details open>
<summary><b>🪣 S3 Bucket (State Storage)</b></summary>

```powershell
aws s3 mb s3://acme-mlfeature-tfstate-dev --region ap-southeast-1
```

**Purpose**: Stores Terraform state files

</details>

<details open>
<parameter name="summary"><b>🔒 DynamoDB Table (State Locking)</b>
