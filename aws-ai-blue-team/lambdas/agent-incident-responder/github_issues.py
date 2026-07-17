"""
GitHub Issue Creation - Auto-creates incident issues with timeline.
"""
import json
import logging
import time
import urllib.request
import os

logger = logging.getLogger()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "donta-dalpoas/AWS-Blue-Team")


def create_incident_issue(incident_id, finding, classification, status, start_time, error=None):
    """Create a GitHub issue for the incident."""
    severity = classification.get("severity", "P2")
    finding_type = finding.get("finding_type", "Unknown")
    resource_arn = finding.get("resource_arn", "N/A")

    title = f"[{severity}] {finding_type} - {status.capitalize()}"

    body = f"""## Incident Summary
- **Incident ID:** {incident_id}
- **Severity:** {severity}
- **Finding Type:** {finding_type}
- **Affected Resource:** `{resource_arn}`
- **Status:** {status.capitalize()}

## Timeline
| Time (UTC) | Event |
|------------|-------|
| {finding.get('event_time', 'N/A')} | Finding detected by {finding.get('event_source', 'unknown')} |
| {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start_time))} | Incident Responder invoked |
| {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | Remediation {status} |

## Classification
- **Score:** {classification.get('score', 'N/A')}
- **Factors:** {json.dumps(classification.get('factors', []), indent=2)}

## Forensic Evidence
- **Pre-state:** `s3://{os.environ.get('S3_BUCKET_NAME', 'bucket')}/forensics/{incident_id}/pre/`
- **Post-state:** `s3://{os.environ.get('S3_BUCKET_NAME', 'bucket')}/forensics/{incident_id}/post/`
"""

    if error:
        body += f"\n## Error\n```\n{error}\n```\n"

    labels = ["incident", f"severity:{severity}"]
    if status == "remediated":
        labels.append("auto-remediated")
    else:
        labels.append("needs-human")

    # Log the issue (actual GitHub API call requires PAT)
    logger.info("GITHUB_ISSUE: title=%s, labels=%s", title, labels)
    logger.info("GITHUB_ISSUE_BODY: %s", body[:500])

    # TODO: Implement actual GitHub API call when PAT is in Secrets Manager
    # For now, log the issue that would be created
    return f"https://github.com/{GITHUB_REPO}/issues/new"


def close_incident_issue(incident_id, issue_url, mttr_seconds):
    """Close a GitHub issue after successful remediation."""
    logger.info(
        "GITHUB_CLOSE: incident=%s, mttr=%.2fs, url=%s",
        incident_id, mttr_seconds, issue_url,
    )
    # TODO: Close via GitHub API when PAT is configured
