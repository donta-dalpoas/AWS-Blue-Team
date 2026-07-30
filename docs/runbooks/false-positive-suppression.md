# Runbook: False Positive Suppression

## Overview

This runbook describes how to identify, create, test, and deploy suppression rules to prevent known false positives from generating alerts and consuming SOC Agent resources.

## Prerequisites

- Access to the GitHub repository
- Familiarity with the detection rule YAML format
- Python 3.11+ installed locally for testing
- AWS CLI configured (for verification)

---

## Step 1: Identify a False Positive

### Indicators of a False Positive

- Same alert firing repeatedly for a known-safe resource
- Alert triggered by expected automation (e.g., CI/CD pipelines)
- Alert from a trusted service account performing normal operations
- Security team confirms the activity is legitimate

### Gather Information

Before suppressing, document:
- **Alert ID / Rule ID** that fired (e.g., `DET-001`)
- **Reason** it's a false positive (e.g., "Jenkins service account runs from this IP")
- **Scope** of suppression (specific resource, account, IP, etc.)
- **Expiry** — should this suppression be permanent or time-limited?

---

## Step 2: Create a Suppression Rule

### File Location

Suppression rules live in: `detections/suppressions/`

### File Format

Create a new YAML file: `detections/suppressions/{descriptive-name}.yml`

```yaml
# Suppression Rule: Jenkins CI API Calls
id: SUP-001
name: Suppress Jenkins CI Service Account API Calls
description: >
  Jenkins service account (arn:aws:iam::ACCOUNT_ID:role/jenkins-ci)
  makes authorized API calls that trigger DET-001. These are expected
  as part of the CI/CD pipeline.
  
suppresses:
  - rule_id: DET-001
    conditions:
      userIdentity.arn: "arn:aws:iam::123456789012:role/jenkins-ci"

# OR more complex conditions:
#  - rule_id: DET-001
#    conditions:
#      sourceIPAddress: "10.0.1.0/24"
#      userIdentity.type: "AssumedRole"
#      userAgent: "jenkins/*"

created_by: your-name
created_date: "2026-07-27"
expires: null  # or "2026-12-31" for time-limited suppressions
approved_by: team-lead-name
reason: "Jenkins CI/CD pipeline triggers this detection during normal deployments"
```

### Naming Convention

- File name: `{source}-{short-description}.yml`
- Examples: `jenkins-ci-api-calls.yml`, `datadog-agent-describe.yml`

---

## Step 3: Test the Suppression Locally

### Run the Detection Matrix Generator

```bash
cd aws-ai-blue-team
python scripts/generate-detection-matrix.py
```

Verify the matrix still generates correctly (suppressions don't break doc generation).

### Validate YAML Syntax

```bash
python -c "
import yaml
from pathlib import Path
for f in Path('detections/suppressions').glob('*.yml'):
    with open(f) as fh:
        data = yaml.safe_load(fh)
        assert 'id' in data, f'{f}: missing id'
        assert 'suppresses' in data, f'{f}: missing suppresses'
        print(f'  OK: {f.name}')
"
```

### Test Against Sample Alert

```bash
# If you have the SOC agent test harness available:
python -m tests.soc_agent.test_suppressions \
  --suppression detections/suppressions/your-new-rule.yml \
  --sample-alert tests/soc_agent/fixtures/sample-alert-det001.json
```

---

## Step 4: Deploy via CI/CD

### Create a Pull Request

```bash
git checkout -b suppress/jenkins-ci-api-calls
git add detections/suppressions/jenkins-ci-api-calls.yml
git commit -m "feat(detections): add suppression for Jenkins CI API calls

Suppresses DET-001 for the Jenkins service account role which triggers
false positives during normal CI/CD pipeline deployments.

Approved-by: team-lead-name
Closes #XX"
git push origin suppress/jenkins-ci-api-calls
```

### PR Requirements

- [ ] YAML is valid (CI will check)
- [ ] `reason` field is filled in
- [ ] `approved_by` field has a name (get verbal approval first)
- [ ] Expiry date set if this is temporary
- [ ] PR description explains the false positive

### Merge and Deploy

1. PR passes CI checks (including `docs-regen` workflow)
2. Reviewer approves
3. Merge to `main`
4. CI/CD deploys updated detection configuration to the SOC Agent

---

## Step 5: Verification

After merge, verify the suppression is active:

### Check Agent Logs

```bash
# Wait for next alert of this type, or trigger a synthetic test
aws logs filter-log-events \
  --log-group-name "/aws/lambda/aws-ai-blue-team-dev-soc-triage" \
  --start-time $(date -u -d '30 minutes ago' +%s)000 \
  --filter-pattern "suppressed" \
  --region us-east-1
```

### Monitor for Recurrence

- Check the **SOC Alerts** Teams channel over the next 24 hours
- If the same alert type continues to fire for the suppressed resource, the suppression may not be matching correctly

### Verify in OpenSearch

```json
GET security-findings-*/_search
{
  "query": {
    "bool": {
      "must": [
        { "term": { "rule_id.keyword": "DET-001" }},
        { "term": { "suppressed": true }},
        { "range": { "@timestamp": { "gte": "now-1h" }}}
      ]
    }
  }
}
```

---

## Removing a Suppression

When a suppression is no longer needed:

1. Delete the YAML file from `detections/suppressions/`
2. Create a PR with explanation of why it's being removed
3. Merge — the detection will start firing again for the previously suppressed source

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Suppression not working | Condition field name doesn't match alert field | Check exact field names in sample alerts |
| YAML parse error in CI | Invalid YAML syntax | Run `yamllint` locally |
| Too many suppressions | Over-suppressing | Review and consolidate; consider tuning the detection rule instead |
| Suppression expired but still active | Agent cached old config | Redeploy the agent Lambda |

---

*Last reviewed: 2026-07-27*
*Owner: Platform Security Team*
