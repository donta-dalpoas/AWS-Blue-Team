# Epic 5 Deployment Guide - GitHub Only

## Overview

This simplified guide deploys the Executive Summary Agent to **commit weekly reports to GitHub only** (no Teams/Slack integration).

---

## Prerequisites

- [x] AWS account with valid credentials configured (`aws configure`)
- [x] Terraform v1.5+ installed
- [x] Git installed  
- [x] GitHub write access to `donta-dalpoas/AWS-Blue-Team`
- [x] Epics 1-4 infrastructure deployed (OpenSearch, SNS topics, etc.)

---

## Step 1: Push Code to GitHub

```bash
cd C:\temp\OpencodeIRAD\aws-ai-blue-team

git status
git add .
git commit -m "feat(epic5): auto-documentation pipeline, executive summary agent (GitHub-only), handover package"
git push origin main
```

---

## Step 2: Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Name: `executive-summary-agent`
4. Scopes: check **`repo`** (full control of private repos)
5. Click **Generate token**
6. **Copy and save the token** (you won't see it again)

---

## Step 3: Set GitHub Repository Secrets

1. Go to https://github.com/donta-dalpoas/AWS-Blue-Team/settings/secrets/actions
2. Click **New repository secret**
3. Add:

| Secret Name | Value |
|-------------|-------|
| `DOCS_BOT_TOKEN` | Your GitHub PAT from Step 2 |
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_REGION` | `us-east-1` |

---

## Step 4: Prepare Terraform Variables

### Add required variable to `terraform/variables.tf`:

```bash
cd terraform
```

Add this at the bottom of `variables.tf`:

```hcl
variable "github_token" {
  description = "GitHub PAT for executive-summary-agent to commit weekly reports"
  type        = string
  sensitive   = true
}
```

### Create secrets file:

Create `terraform/environments/dev/secrets.tfvars` (DO NOT commit this):

```hcl
github_token = "ghp_YOUR_TOKEN_HERE"
```

---

## Step 5: Uncomment the Executive Summary Module

Edit `terraform/main.tf` — find the commented `module "executive_summary"` block at the bottom and **remove the `#` comment markers**:

```hcl
module "executive_summary" {
  source                = "./modules/executive-summary"
  name_prefix           = local.name_prefix
  account_id            = local.account_id
  aws_region            = var.aws_region
  opensearch_endpoint   = module.opensearch.endpoint
  opensearch_domain_arn = module.opensearch.domain_arn
  github_token          = var.github_token
  github_repo           = "${var.github_org}/${var.github_repo}"
  sns_alert_topic_arn   = module.sns.alert_topic_arn
}
```

---

## Step 6: Deploy with Terraform

```bash
terraform init

terraform plan \
  -var-file="environments/dev/terraform.tfvars" \
  -var-file="environments/dev/secrets.tfvars"

terraform apply \
  -var-file="environments/dev/terraform.tfvars" \
  -var-file="environments/dev/secrets.tfvars"
```

Type `yes` when prompted.

---

## Step 7: Verify Deployment

### Check Lambda exists:

```bash
aws lambda get-function \
  --function-name "aws-ai-blue-team-dev-executive-summary" \
  --region us-east-1
```

### Check EventBridge schedule:

```bash
aws events describe-rule \
  --name "aws-ai-blue-team-dev-executive-summary-schedule" \
  --region us-east-1
```

### Manually invoke the Lambda:

```bash
aws lambda invoke \
  --function-name "aws-ai-blue-team-dev-executive-summary" \
  --payload '{"source": "manual-test"}' \
  --region us-east-1 \
  output.json

cat output.json
```

### Check CloudWatch Logs:

```bash
aws logs tail "/aws/lambda/aws-ai-blue-team-dev-executive-summary" \
  --since 5m \
  --follow \
  --region us-east-1
```

### Verify the report was committed:

Check https://github.com/donta-dalpoas/AWS-Blue-Team/tree/main/docs/weekly-reports for a new `YYYY-MM-DD.md` file.

---

## Step 8: Test the Docs Pipeline

1. Go to https://github.com/donta-dalpoas/AWS-Blue-Team/actions
2. Click **docs-regen** workflow
3. Click **Run workflow** → `main` → **Run workflow**
4. Wait for green checkmark
5. Verify these files were generated/updated:
   - `docs/detection-matrix.md`
   - `docs/architecture-inventory.md`
   - `docs/agent-capabilities.md`
   - `docs/cedar-policy-summary.md`

---

## Step 9: Tag the Release

```bash
git pull origin main
git tag -a v1.0 -m "v1.0 - AWS AI Blue Team Platform (Epics 1-5)"
git push origin v1.0
```

Go to https://github.com/donta-dalpoas/AWS-Blue-Team/releases/new and create a release from the `v1.0` tag. Paste the summary from `CHANGELOG.md`.

---

## Done!

- [x] Executive Summary Agent runs every Monday 8AM UTC
- [x] Weekly brief commits to `docs/weekly-reports/YYYY-MM-DD.md`
- [x] Docs auto-regenerate on every merge to `main`
- [x] Repo tagged v1.0
- [x] Runbooks available for permanent team

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `docs-regen` fails | Check `DOCS_BOT_TOKEN` secret |
| Lambda returns 500 | Check CloudWatch Logs; verify OpenSearch endpoint |
| GitHub commit fails | Verify token has `repo` scope; check token expiry |
| Terraform plan fails | Run `terraform init`; verify AWS credentials |
| EventBridge not firing | Check rule is `ENABLED` in AWS console |
