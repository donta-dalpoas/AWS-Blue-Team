# Runbook: Cedar Policy Update

## Overview

This runbook describes how to modify, test, and deploy Cedar authorization policies that control what actions each security agent is permitted or forbidden to perform.

**CAUTION:** Cedar policies are security-critical. An overly permissive policy could allow an agent to perform destructive actions. An overly restrictive policy could prevent an agent from responding to threats.

## Prerequisites

- Access to the GitHub repository
- Cedar CLI installed locally (`cedar-policy-cli`)
- Understanding of the agent architecture and Cedar policy language
- Approval from the team lead for any permission changes

---

## Step 1: Understand the Policy Structure

### File Location

Cedar policies live in: `policies/cedar/`

### Existing Policies

| File | Agent | Purpose |
|------|-------|---------|
| `soc-agent.cedar` | SOC Agent | Read/classify findings, cannot remediate |
| `incident-responder.cedar` | Incident Responder | Containment/remediation, cannot delete |
| `compliance-auditor.cedar` | Compliance Auditor | Read-only config scanning |
| `threat-hunter.cedar` | Threat Hunter | Query logs, create detections |
| `executive-summary.cedar` | Executive Summary | Read metrics only |

### Policy Format

```cedar
// @agent: Agent Name
// @description: What this policy does
// @allows: Action1, Action2
// @denies: Action3, Action4

permit (
    principal == Agent::"agent-name",
    action in [Action::"ActionName", Action::"ActionName2"],
    resource in ResourceType::"scope"
);

forbid (
    principal == Agent::"agent-name",
    action in [Action::"DangerousAction"],
    resource in ResourceType::"scope"
);
```

### Key Principles

1. **Least privilege** — only grant what's needed
2. **Explicit deny** — always forbid dangerous actions explicitly
3. **Annotations** — keep `@allows` and `@denies` comments in sync with actual policy
4. **One file per agent** — each agent has its own policy file

---

## Step 2: Modify a Policy

### Adding a New Permission

Example: Allow the SOC Agent to also query Athena:

```diff
 permit (
     principal == Agent::"soc-agent",
     action in [
         Action::"ReadFinding",
         Action::"ClassifyFinding",
         Action::"EnrichFinding",
         Action::"RouteFinding",
         Action::"QueryOpenSearch",
         Action::"PostTeams",
         Action::"CreateIncident",
-        Action::"UpdateIncident"
+        Action::"UpdateIncident",
+        Action::"QueryAthena"
     ],
     resource in SecurityFindings::"all"
 );
```

Update the annotation comment too:
```diff
-// @allows: ReadFinding, ClassifyFinding, EnrichFinding, RouteFinding, QueryOpenSearch, PostTeams
+// @allows: ReadFinding, ClassifyFinding, EnrichFinding, RouteFinding, QueryOpenSearch, PostTeams, QueryAthena
```

### Removing a Permission

Simply remove the action from the `permit` block and update annotations.

### Adding a New Deny

```cedar
forbid (
    principal == Agent::"soc-agent",
    action == Action::"QueryAthena",
    resource in ProductionData::"pii"
) when {
    resource.classification == "PII"
};
```

---

## Step 3: Test with Cedar CLI

### Install Cedar CLI

```bash
# Via cargo (Rust package manager)
cargo install cedar-policy-cli

# Or download from releases:
# https://github.com/cedar-policy/cedar/releases
```

### Validate Policy Syntax

```bash
cedar validate \
  --schema policies/cedar/schema.cedarschema \
  --policies policies/cedar/soc-agent.cedar
```

### Test Authorization Decisions

Create a test request file `test-request.json`:

```json
{
  "principal": "Agent::\"soc-agent\"",
  "action": "Action::\"QueryAthena\"",
  "resource": "SecurityFindings::\"all\"",
  "context": {}
}
```

```bash
cedar authorize \
  --policies policies/cedar/ \
  --entities policies/cedar/entities.json \
  --request-json test-request.json
```

Expected output: `ALLOW` or `DENY`

### Run the Full Test Suite

```bash
# If test fixtures exist:
python -m pytest tests/ -k "cedar" -v

# Or validate all policies:
for policy in policies/cedar/*.cedar; do
  echo "Validating: ${policy}"
  cedar validate --policies "${policy}" && echo "  PASS" || echo "  FAIL"
done
```

---

## Step 4: Deploy via CI/CD

### Create a Pull Request

```bash
git checkout -b policy/soc-agent-add-athena
git add policies/cedar/soc-agent.cedar
git commit -m "feat(policy): allow SOC Agent to query Athena

Adds QueryAthena permission to the SOC Agent for log investigation.
Scoped to SecurityFindings resources only - cannot query production data.

Approved-by: team-lead-name
Risk: Low (read-only addition)"
git push origin policy/soc-agent-add-athena
```

### PR Requirements

- [ ] Cedar syntax is valid (CI checks this)
- [ ] Annotations (`@allows`, `@denies`) match actual policy
- [ ] No `forbid` rules were removed without explicit justification
- [ ] Team lead approval obtained
- [ ] `cedar-policy-summary.md` will auto-update on merge

### Merge and Deploy

1. PR passes CI (including `docs-regen` which updates `cedar-policy-summary.md`)
2. Reviewer approves (minimum 1 reviewer required)
3. Merge to `main`
4. Cedar evaluator Lambda picks up new policies automatically

---

## Step 5: Verification

### Verify Policy Loaded

```bash
# Check the Cedar evaluator Lambda logs after deployment
aws logs filter-log-events \
  --log-group-name "/aws/lambda/aws-ai-blue-team-dev-cedar-evaluator" \
  --start-time $(date -u -d '10 minutes ago' +%s)000 \
  --filter-pattern "policy loaded" \
  --region us-east-1
```

### Test the New Permission End-to-End

```bash
# Invoke the agent with a test event that exercises the new permission
aws lambda invoke \
  --function-name "aws-ai-blue-team-dev-soc-triage" \
  --payload '{"source": "test", "test_action": "QueryAthena"}' \
  --region us-east-1 \
  /tmp/test-response.json

cat /tmp/test-response.json
```

### Verify Auto-Generated Documentation

After merge, check that `docs/cedar-policy-summary.md` was updated:
- The new action should appear in the policy matrix table
- The agent's allowed/denied lists should reflect the change

---

## Step 6: Rollback

If a policy change causes issues:

### Quick Rollback (Revert Commit)

```bash
git revert HEAD  # if the bad commit is the latest
git push origin main
```

### Emergency: Disable Agent

If an agent is taking unauthorized actions due to a permissive policy:

```bash
# Immediately disable the agent's EventBridge rule
aws events disable-rule \
  --name "aws-ai-blue-team-dev-soc-triage-trigger" \
  --region us-east-1

# Or set Lambda concurrency to 0 (prevents invocation)
aws lambda put-function-concurrency \
  --function-name "aws-ai-blue-team-dev-soc-triage" \
  --reserved-concurrent-executions 0 \
  --region us-east-1
```

Then investigate and fix the policy before re-enabling.

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Agent getting DENY for allowed action | Policy syntax error | Validate with Cedar CLI |
| Policy not taking effect | Lambda using cached version | Redeploy the cedar-evaluator Lambda |
| `cedar validate` fails | Schema mismatch | Update schema file to include new actions/resources |
| Agent performing forbidden action | Missing `forbid` rule | Add explicit deny and redeploy immediately |
| Auto-doc shows wrong permissions | Annotation comments out of sync | Update `@allows`/`@denies` comments |

---

## Security Considerations

- **Never** remove a `forbid` rule without explicit justification and team lead approval
- **Never** grant `ModifyIAM`, `DeleteResource`, or `DisableCloudTrail` to read-only agents
- **Always** scope resource access as narrowly as possible
- **Always** test policy changes in dev before promoting to prod
- Policy changes are audited via git history and the auto-generated `cedar-policy-summary.md`

---

*Last reviewed: 2026-07-27*
*Owner: Platform Security Team*
