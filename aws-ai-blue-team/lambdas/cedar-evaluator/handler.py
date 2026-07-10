"""
Cedar Policy Evaluator Lambda
Loads Cedar policies from S3 and evaluates authorization decisions.
"""
import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

POLICY_BUCKET = os.environ.get("POLICY_BUCKET", "")
POLICY_PREFIX = os.environ.get("POLICY_PREFIX", "cedar/")

s3_client = boto3.client("s3")

# In-memory policy cache (loaded on cold start)
_policies = {}


def load_policies():
    """Load all Cedar policy files from S3 into memory."""
    global _policies
    if _policies:
        return _policies

    try:
        resp = s3_client.list_objects_v2(
            Bucket=POLICY_BUCKET, Prefix=POLICY_PREFIX
        )
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".cedar") or key.endswith(".json"):
                body = s3_client.get_object(Bucket=POLICY_BUCKET, Key=key)
                content = body["Body"].read().decode("utf-8")
                policy_name = key.split("/")[-1].replace(".cedar", "").replace(".json", "")
                _policies[policy_name] = content
                logger.info("Loaded policy: %s", policy_name)
    except ClientError as e:
        logger.error("Failed to load policies: %s", str(e))

    return _policies


def lambda_handler(event, context):
    """Evaluate a Cedar policy decision.
    
    Input: { "principal": "...", "action": "...", "resource": "...", "context": {} }
    Output: { "decision": "ALLOW"|"DENY", "reasons": [...] }
    """
    # Load policies on cold start
    policies = load_policies()

    principal = event.get("principal", "")
    action = event.get("action", "")
    resource = event.get("resource", "")
    context = event.get("context", {})

    logger.info(
        "Evaluating: principal=%s, action=%s, resource=%s",
        principal, action, resource,
    )

    # Simple policy evaluation logic (placeholder for full Cedar engine)
    # In production, use cedarpy or call Amazon Verified Permissions
    decision = evaluate_policies(principal, action, resource, context, policies)

    logger.info(
        "Decision: %s for %s -> %s on %s",
        decision["decision"], principal, action, resource,
    )

    return decision


def evaluate_policies(principal, action, resource, context, policies):
    """Evaluate loaded policies against the request.
    
    This is a simplified evaluator. In production, integrate with:
    - cedarpy (Python Cedar bindings)
    - Amazon Verified Permissions API
    - Or the Cedar CLI via subprocess
    """
    # Default deny
    decision = "DENY"
    reasons = []

    # Simple agent-to-action mapping for MVP
    allowed_actions = {
        "soc-analyst": ["query", "invoke"],
        "incident-responder": ["remediate", "query"],
        "threat-hunter": ["query", "scan"],
        "compliance-auditor": ["scan", "remediate"],
        "red-team": ["attack"],
    }

    # Extract agent name from principal
    agent_name = principal.split("::")[-1].strip('"') if "::" in principal else principal

    if agent_name in allowed_actions:
        # Extract action type
        action_type = action.split("::")[-1].strip('"') if "::" in action else action

        if action_type in allowed_actions[agent_name]:
            decision = "ALLOW"
            reasons.append(f"Policy permits {agent_name} to {action_type}")
        else:
            reasons.append(f"No policy permits {agent_name} to {action_type}")
    else:
        reasons.append(f"Unknown agent: {agent_name}")

    # Check for explicit deny on non-test resources for red-team
    if agent_name == "red-team" and decision == "ALLOW":
        resource_tags = context.get("resource_tags", {})
        if resource_tags.get("Environment") != "test":
            decision = "DENY"
            reasons = [f"Red team agent denied access to non-test resource"]

    return {
        "decision": decision,
        "reasons": reasons,
        "principal": principal,
        "action": action,
        "resource": resource,
    }
