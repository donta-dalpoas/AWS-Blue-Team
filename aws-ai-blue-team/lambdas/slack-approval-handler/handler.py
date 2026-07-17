"""
Slack Approval Handler - Receives interactive button clicks from Slack.
"""
import json
import logging
import time
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PENDING_TABLE = os.environ.get("PENDING_APPROVALS_TABLE", "")
IR_AGENT_FUNCTION = os.environ.get("IR_AGENT_FUNCTION_NAME", "agent-incident-responder")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    """Handle Slack interactive message callbacks."""
    # Parse API Gateway v2 event
    body = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)

    if is_base64:
        import base64
        body = base64.b64decode(body).decode("utf-8")

    # Slack sends URL-encoded form data
    if "payload=" in body:
        from urllib.parse import unquote
        payload_str = body.split("payload=")[1]
        payload = json.loads(unquote(payload_str))
    else:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Could not parse request body")
            return response(400, {"error": "Invalid payload"})

    # Extract action and incident info
    actions = payload.get("actions", [])
    if not actions:
        return response(400, {"error": "No actions in payload"})

    action = actions[0]
    action_id = action.get("action_id", "")
    incident_id = action.get("value", "")
    user = payload.get("user", {})
    user_id = user.get("id", "unknown")
    user_name = user.get("username", "unknown")

    logger.info("Approval action: %s for incident %s by %s", action_id, incident_id, user_name)

    if "approve" in action_id.lower():
        return handle_approve(incident_id, user_id, user_name)
    elif "deny" in action_id.lower():
        return handle_deny(incident_id, user_id, user_name)
    else:
        return response(400, {"error": f"Unknown action: {action_id}"})


def handle_approve(incident_id, user_id, user_name):
    """Process an approval click."""
    table = dynamodb.Table(PENDING_TABLE)

    # Get pending action
    try:
        item = table.get_item(Key={"incident_id": incident_id})
        pending = item.get("Item")
    except Exception as e:
        logger.error("DynamoDB get failed: %s", str(e))
        return response(500, {"error": "Failed to retrieve pending action"})

    if not pending:
        return response(404, {"error": "No pending action found (may have expired)"})

    if pending.get("status") != "pending":
        return response(409, {"error": f"Action already {pending.get('status')}"})

    # Update status
    table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression="SET #s = :s, approver_id = :a, approver_name = :n, approved_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "approved",
            ":a": user_id,
            ":n": user_name,
            ":t": int(time.time()),
        },
    )

    # Invoke IR Agent with the pending action payload
    action_payload = json.loads(pending.get("action_payload", "{}"))
    action_payload["approval"] = {
        "approved_by": user_id,
        "approved_by_name": user_name,
        "approved_at": time.time(),
    }

    try:
        lambda_client.invoke(
            FunctionName=IR_AGENT_FUNCTION,
            InvocationType="Event",
            Payload=json.dumps(action_payload, default=str).encode(),
        )
    except Exception as e:
        logger.error("Failed to invoke IR agent after approval: %s", str(e))
        return response(500, {"error": "Approved but failed to execute"})

    logger.info("APPROVED: incident=%s by %s (%s)", incident_id, user_name, user_id)
    return response(200, {"text": f"Approved by {user_name}. Executing remediation..."})


def handle_deny(incident_id, user_id, user_name):
    """Process a denial click."""
    table = dynamodb.Table(PENDING_TABLE)

    # Update status
    try:
        table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression="SET #s = :s, denier_id = :a, denier_name = :n, denied_at = :t",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "denied",
                ":a": user_id,
                ":n": user_name,
                ":t": int(time.time()),
            },
        )
    except Exception as e:
        logger.error("DynamoDB update failed: %s", str(e))

    logger.info("DENIED: incident=%s by %s (%s)", incident_id, user_name, user_id)
    return response(200, {"text": f"Denied by {user_name}. Manual intervention required."})


def response(status_code, body):
    """Format API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
