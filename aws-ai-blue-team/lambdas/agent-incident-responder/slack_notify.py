"""
Slack Notifications - Post remediation results and approval requests.
"""
import json
import logging
import urllib.request
import os

logger = logging.getLogger()
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def post_remediation_result(incident_id, finding, status, details):
    """Post remediation result to Slack."""
    if not SLACK_WEBHOOK_URL:
        logger.info("Slack webhook not configured - skipping notification")
        return

    finding_type = finding.get("finding_type", "Unknown")
    resource_arn = finding.get("resource_arn", "N/A")

    if status == "remediated":
        emoji = ":white_check_mark:"
        color = "#36a64f"
        title = f"{emoji} Incident Auto-Remediated"
        body = f"*Incident:* `{incident_id}`\n*Finding:* {finding_type}\n*Resource:* `{resource_arn}`\n*Action:* {details.get('action', 'N/A')}\n*MTTR:* {details.get('mttr_seconds', 'N/A')}s"
    elif status == "cedar_denied":
        emoji = ":no_entry:"
        color = "#ff0000"
        title = f"{emoji} Remediation Blocked by Policy"
        body = f"*Incident:* `{incident_id}`\n*Finding:* {finding_type}\n*Resource:* `{resource_arn}`\n*Reason:* Cedar policy evaluation returned DENY\n*Action Required:* Manual intervention needed"
    elif status == "failed":
        emoji = ":x:"
        color = "#ff0000"
        title = f"{emoji} Remediation Failed"
        body = f"*Incident:* `{incident_id}`\n*Finding:* {finding_type}\n*Resource:* `{resource_arn}`\n*Error:* {details}\n*Action Required:* Manual intervention needed"
    else:
        emoji = ":warning:"
        color = "#ffcc00"
        title = f"{emoji} Incident - No Auto-Remediation Available"
        body = f"*Incident:* `{incident_id}`\n*Finding:* {finding_type}\n*Resource:* `{resource_arn}`\n*Status:* {status}\n*Action Required:* Manual review needed"

    message = {
        "text": title,
        "attachments": [{
            "color": color,
            "text": body,
            "footer": f"Incident Responder Agent | {incident_id}",
        }]
    }

    _post_to_slack(message)


def post_approval_request(incident_id, finding, action_description, resource_arn, risk_level):
    """Post an approval request with interactive buttons to Slack."""
    if not SLACK_WEBHOOK_URL:
        logger.info("Slack webhook not configured - skipping approval request")
        return

    message = {
        "text": f":rotating_light: [P1] Incident Requires Approval",
        "attachments": [{
            "color": "#ff0000",
            "text": (
                f"*Incident:* `{incident_id}`\n"
                f"*Finding:* {finding.get('finding_type', 'Unknown')}\n"
                f"*Proposed Action:* {action_description}\n"
                f"*Affected Resource:* `{resource_arn}`\n"
                f"*Risk Level:* {risk_level} - may impact production\n"
                f"*Expires:* 15 minutes"
            ),
            "footer": "Incident Responder Agent - Awaiting Approval",
        }]
    }

    _post_to_slack(message)


def _post_to_slack(message):
    """Send a message to Slack webhook."""
    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        logger.info("Slack notification sent")
    except Exception as e:
        logger.error("Failed to send Slack message: %s", str(e))
