# Changelog

All notable changes to the AWS AI Blue Team project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-07-27

### Release Summary

Initial release of the AWS AI Blue Team automated security monitoring platform. This release delivers a fully autonomous security operations capability with AI-powered agents for detection, response, compliance, and threat hunting — all governed by least-privilege Cedar policies and observable via OpenSearch dashboards.

---

### Epic 1: Foundation Infrastructure

**Goal:** Deploy all core AWS security services, centralized logging, and the AgentCore platform.

#### Added
- KMS encryption key for all security data at rest
- Centralized S3 bucket with lifecycle policies (IA → Glacier → Expiry)
- VPC with dedicated security groups for platform components
- CloudTrail (organization-wide, multi-region)
- VPC Flow Logs for all monitored VPCs
- GuardDuty enabled across all active regions
- SecurityHub with CIS and AWS Foundational benchmarks
- SNS topics for security findings routing
- EventBridge rules for GuardDuty → SNS → Agent routing
- Athena query workgroups for log investigation
- OpenSearch domain (2-node cluster with encryption)
- Log ingestion pipeline (S3 → Lambda → OpenSearch)
- Baseline Generator Lambda (IAM, S3, SG snapshot)
- AgentCore Identity module (IAM roles per agent)
- AgentCore Policy module (Cedar policy evaluator Lambda)
- AgentCore Gateway module (agent invocation routing)

---

### Epic 2: SOC Agent + Incident Responder

**Goal:** Deploy autonomous triage and incident response agents.

#### Added
- SOC Agent Lambda — classifies findings by severity, enriches with context, routes to appropriate responder
- Incident Responder Lambda — performs containment (isolate instance, revoke keys, block IPs) with approval gates for P1/P2
- Microsoft Teams integration for alert notifications and approval workflows
- OpenSearch indices for security findings and incidents
- Detection rules (YAML-based, MITRE ATT&CK mapped)
- Cedar policies enforcing least-privilege per agent

---

### Epic 3: Compliance Auditor + Threat Hunter + Red Team

**Goal:** Deploy proactive security agents for compliance, hunting, and coverage testing.

#### Added
- Compliance Auditor Lambda — scans resource configurations against baselines every 6 hours
- Threat Hunter Lambda — hypothesis-driven log queries, generates new detection rules
- Red Team simulation framework — tests detection coverage against MITRE techniques
- Compliance scorecard dashboard
- Detection coverage map
- Agent-generated detection rules (committed to repo via CI)

---

### Epic 4: Observability + Dashboards

**Goal:** Full operational visibility into agent behavior and security posture.

#### Added
- AgentCore Observability module (X-Ray tracing, CloudWatch metrics)
- 5 OpenSearch dashboards:
  1. SOC Overview (alerts, MTTD, classification)
  2. Incident Response (MTTR, remediations, active incidents)
  3. Compliance Posture (score, violations, drift)
  4. Threat Hunting (runs, rules generated, coverage)
  5. Red Team / Detection Coverage (detection rate, MTTD)
- CloudWatch alarms for agent health (errors, throttles, duration)
- Custom metrics namespace for agent KPIs

---

### Epic 5: Documentation + Handover

**Goal:** Self-documenting system with automated executive reporting and structured team handover.

#### Added
- Auto-Documentation CI Pipeline (`docs-regen` GitHub Actions workflow)
  - `docs/detection-matrix.md` — auto-generated from detection YAML files
  - `docs/architecture-inventory.md` — auto-generated from Terraform modules
  - `docs/agent-capabilities.md` — auto-generated from agent config files
  - `docs/cedar-policy-summary.md` — auto-generated from Cedar policy files
- Executive Summary Agent Lambda
  - Runs every Monday 8AM UTC via EventBridge
  - Queries OpenSearch for 7-day metrics
  - Generates plain-English brief for leadership
  - Posts to **Executive Briefing** Microsoft Teams channel
  - Commits report to `docs/weekly-reports/`
  - Fallback alert if generation fails
- Terraform module for Executive Summary Agent (Lambda + EventBridge + IAM)
- Operational runbooks:
  - `docs/runbooks/all-agents-down.md` — diagnosis and recovery
  - `docs/runbooks/false-positive-suppression.md` — suppression rule lifecycle
  - `docs/runbooks/cedar-policy-update.md` — policy modification workflow
- Handover package:
  - Verification checklist for permanent team
  - Demo recording template
  - CHANGELOG (this file)

---

## Infrastructure Summary

| Component | Count | Notes |
|-----------|-------|-------|
| Lambda Functions | 8 | 5 agents + gateway + evaluator + ingestion |
| EventBridge Rules | 4 | Scheduled + event-driven triggers |
| OpenSearch Domain | 1 | 2-node cluster, encrypted |
| S3 Buckets | 1 | Centralized logging with lifecycle |
| SNS Topics | 2 | Security findings + alerts |
| IAM Roles | 8 | One per Lambda + service roles |
| Cedar Policies | 5 | One per agent |
| Detection Rules | 4+ | Growing via agent-generated rules |
| Dashboards | 5 | OpenSearch Dashboards |

---

## Contributors

- Project Team (Epics 1-5 delivery)
- Permanent Security Team (ongoing operations)

---

*Tagged as `v1.0` at project handover.*
