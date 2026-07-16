"""
Routing Logic - Sends classified findings to the right destination.
P1/P2 -> Incident Responder Agent
P3 -> Slack + log
P4 -> Log only
"""
import json
import logging
import urllib.request

import boto3

from config import get_config

logger = logging.getLogger()
lambda_client = boto3.client("lambda")


def route_finding(finding_meta, enrichment_context, classification):
    """Route the finding based on its severity classification."""
    severity = classification["severity"]

    if severity in ("P1", "P2"):
        route_to_incident_responder(finding_meta, enrichment_context, classification)
    elif severity == "P3":
        route_to_slack(finding_meta, enrichment_context, classification)
    else:
        # P4 - log only (already logged by handler)
        logger.info("P4 finding - log only: %s", finding_meta.get("finding_id"))


def route_to_incident_responder(finding_meta, enrichment_context, classification):
    """Invoke the Incident Responder Agent directly for P1/P2 findings."""
    config = get_config()

    payload = {
        "source": "soc-analyst-agent",
        "finding": finding_meta,
        "enrichment": enrichment_context,
        "classification": classification,
    }

    try:
        response = lambda_client.invoke(
            FunctionName=config.ir_agent_function_name,
            InvocationType="Event",  # Async - don't wait for response
            Payload=json.dumps(payload, default=str).encode("utf-8"),
        )
        logger.info(
            "Routed %s finding to IR agent (status=%d): %s",
            classification["severity"],
            response["StatusCode"],
            finding_meta.get("finding_id"),
        )
    except Exception as e:
        logger.error(
            "Failed to invoke IR agent for %s finding %s: %s",
            classification["severity"],
            finding_meta.get("finding_id"),
            str(e),
        )
        # Fallback: post to Slack as critical alert
        route_to_slack(finding_meta, enrichment_context, classification, fallback=True)


def route_to_slack(finding_meta, enrichment_context, classification, fallback=False):
    """Post a formatted alert summary to Slack."""
    config = get_config()

    if not config.slack_webhook_url:
        logger.info("Slack webhook not configured - skipping Slack notification")
        return

    # Build the message
    severity = classification["severity"]
    emoji = ":rotating_light:" if severity in ("P1", "P2") else ":warning:"
    fallback_note = " [IR AGENT UNAVAILABLE - MANUAL ACTION REQUIRED]" if fallback else ""

    ip_rep = enrichment_context.get("ip_reputation", {})
    baseline = enrichment_context.get("baseline", {})

    message = {
        "text": f"{emoji} [{severity}] Security Finding Detected{fallback_note}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} [{severity}] {finding_meta.get('title', 'Security Finding')}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:* {finding_meta.get('finding_type', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Severity:* {severity} (score: {classification['score']})"},
                    {"type": "mrkdwn", "text": f"*Actor:* `{finding_meta.get('principal_arn', 'N/A')}`"},
                    {"type": "mrkdwn", "text": f"*Resource:* `{finding_meta.get('resource_arn', 'N/A')}`"},
                    {"type": "mrkdwn", "text": f"*Source IP:* {finding_meta.get('source_ip', 'N/A')} (Reputation: {ip_rep.get('abuse_confidence_score', 'N/A')}/100)"},
                    {"type": "mrkdwn", "text": f"*Baseline Deviation:* {'Yes' if not baseline.get('baseline_match', True) else 'No'}"},
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Alert ID: `{finding_meta.get('finding_id', 'N/A')}` | Region: {finding_meta.get('region', 'N/A')}"}
                ]
            }
        ]
    }

    try:
        req = urllib.request.Request(
            config.slack_webhook_url,
            data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        logger.info("Slack notification sent for %s finding %s", severity, finding_meta.get("finding_id"))
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", str(e))
