# Runbook: All Agents Down

## Overview

This runbook covers diagnosis and recovery when one or more security agents stop running. Use this when alerts stop flowing, dashboards show no data, or you suspect agents have failed.

## Prerequisites

- AWS CLI configured with appropriate IAM role
- Access to AWS Console (Lambda, EventBridge, CloudWatch)
- Access to the GitHub repository for CI/CD re-deployment

## Severity

**P1** — If all agents are down simultaneously, no security monitoring is active.

---

## Step 1: Determine Which Agents Are Not Running

### Check Lambda Invocation Metrics

```bash
# Check invocations for each agent in the last 2 hours
AGENTS=("soc-triage" "incident-responder" "compliance-auditor" "threat-hunter" "executive-summary")
REGION="us-east-1"
NAME_PREFIX="aws-ai-blue-team-dev"

for AGENT in "${AGENTS[@]}"; do
  echo "=== ${AGENT} ==="
  aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value="${NAME_PREFIX}-${AGENT}" \
    --start-time $(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum \
    --region ${REGION}
done
```

### Check for Errors

```bash
for AGENT in "${AGENTS[@]}"; do
  echo "=== ${AGENT} Errors ==="
  aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --dimensions Name=FunctionName,Value="${NAME_PREFIX}-${AGENT}" \
    --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum \
    --region ${REGION}
done
```

### Check Recent CloudWatch Logs

```bash
aws logs tail /aws/lambda/${NAME_PREFIX}-soc-triage \
  --since 1h \
  --region ${REGION}
```

---

## Step 2: Check EventBridge Schedule Health

```bash
# List all scheduled rules
aws events list-rules \
  --name-prefix "${NAME_PREFIX}" \
  --region ${REGION}

# Check specific rule state
aws events describe-rule \
  --name "${NAME_PREFIX}-executive-summary-schedule" \
  --region ${REGION}

# Verify targets are attached
aws events list-targets-by-rule \
  --rule "${NAME_PREFIX}-executive-summary-schedule" \
  --region ${REGION}
```

### Common Issues
- Rule state is `DISABLED` — re-enable with `aws events enable-rule`
- Target Lambda ARN is stale after redeployment — redeploy via CI/CD
- IAM permission removed — check Lambda resource-based policy

---

## Step 3: Check SNS Topic Health (for event-driven agents)

```bash
# Check SNS topic exists and has subscriptions
aws sns list-subscriptions-by-topic \
  --topic-arn "arn:aws:sns:${REGION}:ACCOUNT_ID:${NAME_PREFIX}-security-findings" \
  --region ${REGION}

# Check for delivery failures
aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfNotificationsFailed \
  --dimensions Name=TopicName,Value="${NAME_PREFIX}-security-findings" \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --region ${REGION}
```

---

## Step 4: Manually Invoke an Agent for Testing

```bash
# Invoke the SOC Agent with a test event
aws lambda invoke \
  --function-name "${NAME_PREFIX}-soc-triage" \
  --payload '{"source": "manual-test", "detail-type": "test-invocation"}' \
  --region ${REGION} \
  /tmp/soc-response.json

cat /tmp/soc-response.json

# Invoke Executive Summary Agent
aws lambda invoke \
  --function-name "${NAME_PREFIX}-executive-summary" \
  --payload '{"source": "manual-test", "detail-type": "weekly-executive-summary"}' \
  --region ${REGION} \
  /tmp/exec-response.json

cat /tmp/exec-response.json
```

### Check for Throttling

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Throttles \
  --dimensions Name=FunctionName,Value="${NAME_PREFIX}-soc-triage" \
  --start-time $(date -u -d '6 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region ${REGION}
```

---

## Step 5: Redeploy All Agents from Scratch via CI/CD

If agents are in an unrecoverable state, redeploy from the repository:

### Option A: Trigger CI/CD Pipeline

1. Go to the GitHub repository: `https://github.com/donta-dalpoas/AWS-Blue-Team`
2. Navigate to **Actions** tab
3. Select the **Deploy Agents** workflow
4. Click **Run workflow** → select `main` branch
5. Monitor the workflow for successful completion

### Option B: Manual Terraform Redeploy

```bash
# Clone and navigate to terraform directory
git clone https://github.com/donta-dalpoas/AWS-Blue-Team.git
cd AWS-Blue-Team/aws-ai-blue-team/terraform

# Initialize and plan
terraform init
terraform plan -var-file="environments/dev/terraform.tfvars"

# Apply (will recreate any missing/broken resources)
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### Option C: Redeploy a Single Lambda

```bash
# Repackage and deploy a specific Lambda
cd lambdas/executive-summary
zip -r /tmp/executive-summary.zip .

aws lambda update-function-code \
  --function-name "${NAME_PREFIX}-executive-summary" \
  --zip-file fileb:///tmp/executive-summary.zip \
  --region ${REGION}
```

---

## Step 6: Verify Recovery

After redeployment:

1. Manually invoke each agent (Step 4)
2. Check CloudWatch Logs for successful execution
3. Verify OpenSearch is receiving new data
4. Confirm Teams notifications are flowing
5. Wait for next scheduled run and verify automatic execution

---

## Escalation Path

| Time Without Resolution | Action |
|------------------------|--------|
| 15 minutes | Page on-call engineer |
| 30 minutes | Escalate to team lead |
| 1 hour | Engage AWS support (if infrastructure issue) |
| 2 hours | Activate manual monitoring procedures |

---

## Root Cause Categories

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| All agents stopped | IAM role deleted/modified | Redeploy via Terraform |
| Single agent errors | Code bug or dependency issue | Check logs, fix, redeploy |
| No invocations | EventBridge rule disabled | Re-enable rule |
| Throttled | Concurrency limit hit | Increase reserved concurrency |
| Timeout errors | OpenSearch unreachable | Check VPC/security groups |
| Permission denied | KMS key policy changed | Verify key policy |

---

*Last reviewed: 2026-07-27*
*Owner: Platform Security Team*
