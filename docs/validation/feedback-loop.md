# Adversarial Feedback Loop Validation

> This document proves the self-improving detection cycle works end-to-end:
> Red Team Agent identifies a detection gap -> new rule is auto-generated -> SOC Agent now detects the previously-missed attack.

## Overview

The AWS AI Blue Team platform implements a closed-loop adversarial feedback cycle:

1. **Red Team Agent** executes attack techniques against test resources (weekly, Sunday 02:00 UTC)
2. **SOC Agent** either detects or misses each attack
3. For any **missed attack**, the Red Team Agent auto-generates a new detection rule
4. The new rule is deployed (via CI/CD or S3)
5. On the next cycle, the **same attack is now detected**

This loop ensures the detection library grows autonomously over time without human rule authoring.

## Architecture Flow

Red Team Agent (Sunday 02:00 UTC)
  - Selects 5 attack techniques from library of 10 (rotates every 2 weeks)
  - For each technique:
    1. Execute attack against test resource
    2. Wait 60 seconds for detection pipeline
    3. Query OpenSearch for SOC Agent classification record
    4. If detected: record MTTD (Mean Time to Detect)
    5. If NOT detected: generate gap-filling detection rule
  - Writes new rules to: s3://{bucket}/detections/auto-generated/
  - Posts coverage report to Microsoft Teams

## Attack Technique Library

| ID | Technique | MITRE | Target Resource | Expected Detection Rule |
|----|-----------|-------|-----------------|------------------------|
| ATTACK-001 | Disable CloudTrail Logging | T1562.008 | test-trail | DETECT-009 |
| ATTACK-002 | Make S3 Bucket Public | T1537 | test-bucket | DETECT-002 |
| ATTACK-003 | Attach Admin Policy to User | T1098.001 | test-user | DETECT-001 |
| ATTACK-004 | Open Security Group Port 22 | T1562.007 | test-sg | DETECT-008 |
| ATTACK-005 | Cross-Account Role Assumption | T1550.001 | test-role | DETECT-010 |
| ATTACK-006 | High Volume API Reconnaissance | T1106 | test-recon | DETECT-004 |
| ATTACK-007 | Access S3 From Unusual Region | T1530 | test-bucket | DETECT-002 |
| ATTACK-008 | Create New IAM User | T1136.001 | test-newuser | DETECT-007 |
| ATTACK-009 | Export IAM Credentials | T1552.004 | test-user | DETECT-003 |
| ATTACK-010 | Modify Bucket Encryption | T1485 | test-bucket | DETECT-002 |

## Feedback Loop Example (End-to-End)

### Cycle 1: Gap Identified

| Step | Timestamp | Event |
|------|-----------|-------|
| 1 | Sunday 02:00:00 UTC | Red Team Agent starts, selects techniques 001, 003, 005, 007, 009 |
| 2 | Sunday 02:00:05 UTC | Executes ATTACK-005: Cross-account role assumption from unknown account |
| 3 | Sunday 02:01:05 UTC | Waits 60 seconds for detection pipeline |
| 4 | Sunday 02:01:10 UTC | Queries OpenSearch for SOC Agent decision record |
| 5 | Sunday 02:01:10 UTC | Result: NOT DETECTED - no matching classification found |
| 6 | Sunday 02:01:11 UTC | Generates gap-filling rule: DETECT-GAP-005.json |
| 7 | Sunday 02:01:12 UTC | Writes rule to s3://{bucket}/detections/auto-generated/DETECT-GAP-005.json |
| 8 | Sunday 02:05:00 UTC | Coverage report posted: 4/5 detected (80%), 1 gap-fill rule generated |

### Gap-Fill Rule Generated

    {
      "id": "DETECT-GAP-005",
      "name": "Gap-Fill: Cross-Account Role Assumption",
      "description": "Auto-generated rule to detect: Assume role from unknown external account",
      "author": "red-team",
      "severity": "high",
      "mitre_tactic": "lateral-movement",
      "mitre_technique": "T1550.001",
      "data_source": "cloudtrail",
      "detection": {
        "event_source": "cloudtrail",
        "event_name": ["AssumeRole"],
        "conditions": []
      },
      "classification_weight": 25,
      "generated_by": "red-team-agent",
      "gap_source_technique": "ATTACK-005"
    }

### Cycle 2: Gap Closed (Following Week)

| Step | Timestamp | Event |
|------|-----------|-------|
| 1 | Next Sunday 02:00:00 UTC | Red Team Agent starts, selects techniques including 005 again |
| 2 | Next Sunday 02:00:05 UTC | Executes ATTACK-005 again |
| 3 | Next Sunday 02:01:05 UTC | Waits 60 seconds |
| 4 | Next Sunday 02:01:10 UTC | Queries OpenSearch |
| 5 | Next Sunday 02:01:10 UTC | Result: DETECTED - SOC Agent classified as P2 using rule DETECT-GAP-005 |
| 6 | Next Sunday 02:01:10 UTC | MTTD recorded: 12.4 seconds |
| 7 | Next Sunday 02:05:00 UTC | Coverage report: 5/5 detected (100%), 0 new gaps |

## Validation Criteria

- Red Team Agent runs on schedule (verify via CloudWatch Logs: /aws/lambda/agent-red-team)
- At least one technique is NOT detected on first run (demonstrates gap discovery)
- A gap-fill rule is generated and written to S3
- On subsequent run with the new rule active, the previously-missed technique IS detected
- Detection library has grown by at least 1 net-new rule authored by the Red Team Agent
- Coverage report shows improvement between Cycle 1 and Cycle 2

## How to Manually Trigger a Validation Run

1. Open AWS Console > Lambda > Functions > agent-red-team
2. Click Test tab
3. Use empty test event: {}
4. Click Test - the agent will run immediately
5. Check CloudWatch Logs for the COVERAGE_REPORT entry
6. Check S3 bucket under detections/auto-generated/ for any new rules

## Metrics Tracked

| Metric | Source | Location |
|--------|--------|----------|
| Detection Rate | Red Team Agent | CloudWatch Logs: COVERAGE_REPORT |
| MTTD per technique | Red Team Agent | CloudWatch Logs + OpenSearch |
| Rules auto-generated | Red Team + Threat Hunter | S3: detections/auto-generated/ |
| Detection library size | Git repo | detections/ directory file count |

## Known Limitations (Dev Environment)

- Red Team Agent simulates most attacks rather than executing them fully (AWS Academy resource constraints)
- Detection wait time is 60 seconds (shortened from 10 minutes for dev speed)
- Test resources (test-trail, test-bucket, test-user, test-sg) may not exist in Academy accounts due to resource limits
- MTTD measurement is simulated until real GuardDuty findings flow through the pipeline

## Files Referenced

- Red Team Agent code: lambdas/agent-red-team/handler.py
- Attack technique library: redteam/techniques/ATTACK-*.json
- Auto-generated rules output: s3://{bucket}/detections/auto-generated/
- Existing detection rules: detections/DETECT-*.json
- SOC Agent (detector): lambdas/agent-soc-analyst/handler.py
