"""
Incident Responder Agent - Automated containment for P1/P2 findings.
Executes 4 auto-remediations and manages approval-gated actions.
"""
import json
import logging
import time
import os
import uuid

import boto3
from botocore.exceptions import ClientError

from remediations import (
    remediate_cloudtrail_disabled,
    remediate_s3_public,
    remediate_iam_privilege_escalation,
    remediate_sg_open_to_world,
)
from forensics import capture_pre_state, capture_post_state
from slack_notify import post_approval_request, post_remediation_result
from github_issues import create_incident_issue, close_incident_issue

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "")
CEDAR_EVALUATOR_ARN = os.environ.get("CEDAR_EVALUATOR_ARN", "")
PENDING_TABLE = os.environ.get("PENDING_APPROVALS_TABLE", "")

lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    """Main handler - invoked by SOC Agent on P1/P2 classification."""
    start_time = time.time()
    incident_id = f"INC-{time.strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4]}"

    logger.info("Incident Responder invoked: %s", incident_id)

    # Parse the payload from SOC Agent
    finding = event.get("finding", {})
    enrichment = event.get("enrichment", {})
    classification = event.get("classification", {})

    finding_type = finding.get("finding_type", "")
    resource_arn = finding.get("resource_arn", "")
    severity = classification.get("severity", "P2")

    logger.info(
        "Processing incident %s: type=%s, severity=%s, resource=%s",
        incident_id, finding_type, severity, resource_arn,
    )

    # Determine which remediation applies
    remediation_type = determine_remediation_type(finding_type, finding)

    if not remediation_type:
        logger.warning("No auto-remediation available for finding type: %s", finding_type)
        # Post to Slack for manual handling
        post_remediation_result(incident_id, finding, "no_auto_remediation", None)
        return {"status": "no_remediation", "incident_id": incident_id}

    # Check Cedar policy authorization
    cedar_decision = evaluate_cedar_policy(remediation_type, resource_arn)
    if cedar_decision != "ALLOW":
        logger.warning("Cedar DENIED remediation %s on %s", remediation_type, resource_arn)
        post_remediation_result(incident_id, finding, "cedar_denied", cedar_decision)
        return {"status": "cedar_denied", "incident_id": incident_id}

    # Capture pre-state
    pre_state = capture_pre_state(incident_id, remediation_type, finding, S3_BUCKET)

    # Execute remediation
    try:
        result = execute_remediation(remediation_type, finding, enrichment)
    except Exception as e:
        logger.error("Remediation failed for %s: %s", incident_id, str(e))
        post_remediation_result(incident_id, finding, "failed", str(e))
        create_incident_issue(incident_id, finding, classification, "failed", start_time, str(e))
        return {"status": "failed", "incident_id": incident_id, "error": str(e)}

    # Capture post-state
    post_state = capture_post_state(incident_id, remediation_type, finding, S3_BUCKET)

    # Calculate MTTR
    mttr_seconds = round(time.time() - start_time, 2)

    # Log success
    logger.info(
        "Remediation complete: incident=%s, action=%s, mttr=%.2fs",
        incident_id, remediation_type, mttr_seconds,
    )

    # Create and close GitHub issue
    issue_url = create_incident_issue(
        incident_id, finding, classification, "remediated", start_time, None
    )
    close_incident_issue(incident_id, issue_url, mttr_seconds)

    # Post to Slack
    post_remediation_result(incident_id, finding, "remediated", {
        "action": remediation_type,
        "mttr_seconds": mttr_seconds,
        "resource": resource_arn,
    })

    # Log MTTR decision record
    decision_record = {
        "incident_id": incident_id,
        "severity": severity,
        "finding_type": finding_type,
        "remediation_type": remediation_type,
        "resource_arn": resource_arn,
        "status": "remediated",
        "mttr_seconds": mttr_seconds,
        "cedar_decision": "ALLOW",
        "forensic_path": f"s3://{S3_BUCKET}/forensics/{incident_id}/",
        "timestamp": time.time(),
    }
    logger.info("MTTR_RECORD: %s", json.dumps(decision_record, default=str))

    return {
        "status": "remediated",
        "incident_id": incident_id,
        "action": remediation_type,
        "mttr_seconds": mttr_seconds,
        "forensic_path": f"s3://{S3_BUCKET}/forensics/{incident_id}/",
    }


def determine_remediation_type(finding_type, finding):
    """Determine which auto-remediation to apply based on finding type."""
    ft_lower = finding_type.lower()

    if "cloudtrail" in ft_lower and ("stop" in ft_lower or "disable" in ft_lower or "logging" in ft_lower):
        return "cloudtrail_reenable"
    elif "s3" in ft_lower and ("public" in ft_lower or "policy" in ft_lower or "bucket" in ft_lower):
        return "s3_public_revert"
    elif "iam" in ft_lower and ("policy" in ft_lower or "privilege" in ft_lower or "admin" in ft_lower or "attach" in ft_lower):
        return "iam_detach_disable"
    elif "securitygroup" in ft_lower or ("ec2" in ft_lower and "0.0.0.0" in str(finding)):
        return "sg_revoke"

    return None


def evaluate_cedar_policy(action, resource_arn):
    """Call Cedar evaluator to authorize the remediation action."""
    if not CEDAR_EVALUATOR_ARN:
        logger.warning("Cedar evaluator not configured - allowing by default")
        return "ALLOW"

    try:
        response = lambda_client.invoke(
            FunctionName=CEDAR_EVALUATOR_ARN,
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "principal": "incident-responder",
                "action": "remediate",
                "resource": resource_arn or "unknown",
                "context": {"remediation_type": action},
            }).encode(),
        )
        result = json.loads(response["Payload"].read())
        return result.get("decision", "DENY")
    except Exception as e:
        logger.error("Cedar evaluation failed: %s - defaulting to DENY", str(e))
        return "DENY"


def execute_remediation(remediation_type, finding, enrichment):
    """Execute the appropriate remediation action."""
    if remediation_type == "cloudtrail_reenable":
        return remediate_cloudtrail_disabled(finding)
    elif remediation_type == "s3_public_revert":
        return remediate_s3_public(finding, enrichment)
    elif remediation_type == "iam_detach_disable":
        return remediate_iam_privilege_escalation(finding)
    elif remediation_type == "sg_revoke":
        return remediate_sg_open_to_world(finding)
    else:
        raise ValueError(f"Unknown remediation type: {remediation_type}")
