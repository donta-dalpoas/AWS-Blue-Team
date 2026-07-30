# Handover Verification Checklist

## Purpose

This checklist confirms that the permanent team can independently operate the AWS Blue Team security platform without assistance from the project team. **All items must be completed by a permanent team member (not the project team)** before handover is declared complete.

---

## Verifier Information

| Field | Value |
|-------|-------|
| Permanent Team Member | _________________________ |
| Date | _________________________ |
| Witnessed By (Project Team) | _________________________ |

---

## 1. Alert Lifecycle (End-to-End)

- [ ] **Trigger a synthetic test alert** using the test harness:
  ```bash
  aws lambda invoke \
    --function-name "aws-ai-blue-team-dev-soc-triage" \
    --payload file://tests/soc_agent/fixtures/synthetic-alert.json \
    --region us-east-1 \
    /tmp/test-result.json
  ```
- [ ] **Trace the alert** through the full pipeline:
  - [ ] Alert appears in OpenSearch `security-findings-*` index
  - [ ] SOC Agent triage decision logged (classification, severity)
  - [ ] High-severity alert routed to Incident Responder
  - [ ] Teams notification received in **SOC Alerts** channel
  - [ ] Incident record created in OpenSearch `security-incidents-*`
- [ ] **Explain** the alert lifecycle without assistance

---

## 2. X-Ray Traces

- [ ] Navigate to AWS X-Ray console (`us-east-1`)
- [ ] Locate traces for the SOC Agent (`aws-ai-blue-team-dev-soc-triage`)
- [ ] Identify a trace showing:
  - [ ] Lambda cold start vs. warm start
  - [ ] OpenSearch query duration
  - [ ] Total agent execution time
- [ ] Explain what each segment represents

---

## 3. Suppression Rule Management

- [ ] **Create** a test suppression rule:
  - Create file `detections/suppressions/test-suppression.yml`
  - Suppress a specific rule ID for a test resource
- [ ] **Commit** to a branch and push
- [ ] **Verify** CI passes (YAML validation)
- [ ] **Verify** the suppression takes effect (check logs)
- [ ] **Remove** the test suppression and clean up

---

## 4. Cedar Policy Management

- [ ] Open an existing policy file in `policies/cedar/`
- [ ] **Explain** the difference between `permit` and `forbid` blocks
- [ ] **Validate** a policy using Cedar CLI:
  ```bash
  cedar validate --policies policies/cedar/soc-agent.cedar
  ```
- [ ] Make a test change (add a comment), commit to branch
- [ ] **Verify** the `docs-regen` workflow updates `cedar-policy-summary.md`
- [ ] Revert the test change

---

## 5. OpenSearch Dashboards

Access all 5 dashboards and explain what each metric means:

- [ ] **Dashboard 1: SOC Overview**
  - Total alerts processed (24h/7d/30d)
  - Alert classification breakdown (severity distribution)
  - MTTD (mean time to detect) trend
  
- [ ] **Dashboard 2: Incident Response**
  - MTTR (mean time to respond) p50/p95
  - Auto-remediation vs. approval-gated actions
  - Active incidents by status
  
- [ ] **Dashboard 3: Compliance Posture**
  - Compliance score (% resources in baseline)
  - Violations by category
  - Drift trend over time
  
- [ ] **Dashboard 4: Threat Hunting**
  - Hunt runs executed
  - Detection rules generated
  - Coverage map (MITRE ATT&CK)
  
- [ ] **Dashboard 5: Red Team / Detection Coverage**
  - Techniques simulated
  - Detection rate (%)
  - Mean time to detect simulated attacks

---

## 6. IAM and Access

- [ ] Permanent team member can assume the `SecurityOperator` role
- [ ] Permanent team member has GitHub repository write access
- [ ] Permanent team member can access CloudWatch Logs
- [ ] Permanent team member can access OpenSearch dashboards
- [ ] Permanent team member can access AWS X-Ray
- [ ] Permanent team member can trigger GitHub Actions workflows

---

## 7. CI/CD Operations

- [ ] **Trigger** the `docs-regen` workflow manually from GitHub Actions
- [ ] **Verify** the workflow completes successfully
- [ ] **Trigger** a Terraform plan (review mode) from CI/CD
- [ ] **Understand** the branch protection rules on `main`

---

## Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Permanent Team Lead | | | |
| Permanent Team Member | | | |
| Project Team Lead | | | |
| Project Team Member | | | |

---

### Handover Declared Complete

- [ ] All checklist items above are marked complete
- [ ] All parties have signed off
- [ ] Repository tagged `v1.0`
- [ ] IAM cleanup issue created with scheduled date

---

*Created: 2026-07-27*
*Template version: 1.0*
