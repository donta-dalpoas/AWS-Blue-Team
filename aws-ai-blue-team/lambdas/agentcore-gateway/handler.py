"""
AgentCore Gateway Lambda - Routes agent invocation requests.
"""
import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

POLICY_EVALUATOR_ARN = os.environ.get("POLICY_EVALUATOR_ARN", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    """Handle API Gateway HTTP API v2 events."""
    route_key = event.get("routeKey", "")
    path = event.get("rawPath", "")

    logger.info("Request: %s %s", route_key, path)

    if route_key == "GET /health":
        return health_check()
    elif route_key == "GET /agents":
        return list_agents()
    elif route_key.startswith("POST /invoke"):
        return invoke_agent(event)
    else:
        return response(404, {"error": "Not found"})


def health_check():
    """Return health status of all components."""
    status = {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": ENVIRONMENT,
        "components": {
            "gateway": "healthy",
            "policy_evaluator": check_policy_evaluator(),
            "agent_registry": "healthy",
        },
    }
    return response(200, status)


def check_policy_evaluator():
    """Check if policy evaluator is reachable."""
    if not POLICY_EVALUATOR_ARN:
        return "not_configured"
    try:
        resp = lambda_client.invoke(
            FunctionName=POLICY_EVALUATOR_ARN,
            InvocationType="DryRun",
        )
        return "healthy" if resp["StatusCode"] == 204 else "unhealthy"
    except Exception:
        return "unhealthy"


def list_agents():
    """List registered agents and their status."""
    agents = [
        {"name": "soc-analyst", "status": "registered", "session_type": "harness"},
        {"name": "incident-responder", "status": "registered", "session_type": "harness"},
        {"name": "threat-hunter", "status": "registered", "session_type": "runtime"},
        {"name": "compliance-auditor", "status": "registered", "session_type": "harness"},
        {"name": "red-team", "status": "registered", "session_type": "runtime"},
    ]
    return response(200, {"agents": agents})


def invoke_agent(event):
    """Invoke a target agent after policy evaluation."""
    # Extract agent name from path or body
    path_params = event.get("pathParameters", {}) or {}
    agent_name = path_params.get("agent_name")

    if not agent_name:
        body = json.loads(event.get("body", "{}"))
        agent_name = body.get("agent_name")

    if not agent_name:
        return response(400, {"error": "agent_name is required"})

    # TODO: Policy evaluation via Cedar evaluator
    # TODO: Look up agent Lambda ARN from registry
    # TODO: Invoke target agent

    logger.info("Invoke request for agent: %s", agent_name)

    return response(202, {
        "status": "accepted",
        "agent": agent_name,
        "invocation_id": f"inv-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "message": "Agent invocation queued",
    })


def response(status_code, body):
    """Format API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
