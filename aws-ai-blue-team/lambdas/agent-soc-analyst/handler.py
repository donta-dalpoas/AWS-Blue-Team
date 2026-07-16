"""
SOC Analyst Agent - Main Entry Point
Receives security findings via SNS, enriches them with context,
classifies severity (P1-P4), and routes to appropriate destination.
"""
import json
import logging
import time
import os

from config import Config
from suppression import check_suppression
from enrichment import enrich_finding
from classification import classify_finding
from routing import route_finding
from detection_rules import load_detection_rules, match_rules

logger = logging.getLogger()
logger.setLevel(logging.INFO)

config = Config()
detection_rules = load_detection_rules()


def lambda_handler(event, context):
    """Main handler - invoked by SNS on every security finding."""
    start_time = time.time()

    for record in event.get("Records", []):
        try:
            process_record(record, start_time)
        except Exception as e:
            logger.error("Unhandled error processing record: %s", str(e), exc_info=True)
            # Don't re-raise - prevents entire batch from going to DLQ
            # Individual failures are logged and tracked via metrics

    return {"statusCode": 200}


def process_record(record, start_time):
    """Process a single SNS record containing a security finding."""
    # Parse the SNS message
    sns_message = record.get("Sns", {})
    message_body = sns_message.get("Message", "{}")

    try:
        finding = json.loads(message_body)
    except json.JSONDecodeError:
        logger.error("Failed to parse SNS message as JSON: %s", message_body[:500])
        return

    # Extract finding metadata
    finding_meta = extract_finding_metadata(finding)
    if not finding_meta:
        logger.warning("Could not extract metadata from finding")
        return

    logger.info(
        "Processing finding: type=%s, source=%s, principal=%s",
        finding_meta.get("finding_type"),
        finding_meta.get("event_source"),
        finding_meta.get("principal_arn"),
    )

    # Step 1: Check suppression
    suppression_result = check_suppression(finding_meta)
    if suppression_result["suppressed"]:
        logger.info(
            "Finding suppressed by rule %s: %s",
            suppression_result["rule_id"],
            suppression_result["reason"],
        )
        log_decision(finding_meta, "suppressed", suppression_result, start_time)
        return

    # Step 2: Enrich with context
    enrichment_context = enrich_finding(finding_meta)

    # Step 3: Match detection rules
    matched_rules = match_rules(finding_meta, detection_rules)

    # Step 4: Classify severity
    classification = classify_finding(finding_meta, enrichment_context, matched_rules)

    # Step 5: Route based on severity
    route_finding(finding_meta, enrichment_context, classification)

    # Step 6: Log decision to OpenSearch
    mttd_seconds = time.time() - start_time
    log_decision(finding_meta, classification["severity"], {
        "classification": classification,
        "enrichment": enrichment_context,
        "matched_rules": [r["id"] for r in matched_rules],
        "mttd_seconds": round(mttd_seconds, 2),
    }, start_time)

    logger.info(
        "Finding classified as %s (score=%d, mttd=%.2fs)",
        classification["severity"],
        classification["score"],
        mttd_seconds,
    )


def extract_finding_metadata(finding):
    """Extract normalized metadata from GuardDuty or SecurityHub finding format."""
    # GuardDuty format (via EventBridge)
    if finding.get("source") == "aws.guardduty" or "detail" in finding:
        detail = finding.get("detail", finding)
        return {
            "finding_id": detail.get("id", ""),
            "finding_type": detail.get("type", ""),
            "event_source": "guardduty",
            "severity_raw": float(detail.get("severity", 0)),
            "severity_label": severity_label_from_score(float(detail.get("severity", 0))),
            "title": detail.get("title", ""),
            "description": detail.get("description", ""),
            "principal_arn": extract_principal_from_guardduty(detail),
            "source_ip": extract_ip_from_guardduty(detail),
            "resource_arn": extract_resource_from_guardduty(detail),
            "region": detail.get("region", ""),
            "account_id": detail.get("accountId", ""),
            "event_time": detail.get("updatedAt", detail.get("createdAt", "")),
            "raw_finding": detail,
        }

    # SecurityHub ASFF format
    if finding.get("source") == "aws.securityhub" or "Severity" in finding:
        detail = finding.get("detail", {}).get("findings", [{}])[0] if "detail" in finding else finding
        severity = detail.get("Severity", {})
        return {
            "finding_id": detail.get("Id", ""),
            "finding_type": ",".join(detail.get("Types", [])),
            "event_source": "securityhub",
            "severity_raw": float(severity.get("Normalized", 0)) / 10.0,
            "severity_label": severity.get("Label", "INFORMATIONAL"),
            "title": detail.get("Title", ""),
            "description": detail.get("Description", ""),
            "principal_arn": "",
            "source_ip": "",
            "resource_arn": detail.get("Resources", [{}])[0].get("Id", "") if detail.get("Resources") else "",
            "region": detail.get("Region", ""),
            "account_id": detail.get("AwsAccountId", ""),
            "event_time": detail.get("UpdatedAt", detail.get("CreatedAt", "")),
            "raw_finding": detail,
        }

    # Unknown format - try generic extraction
    return {
        "finding_id": finding.get("id", str(hash(json.dumps(finding, default=str)))[:12]),
        "finding_type": finding.get("type", "unknown"),
        "event_source": "unknown",
        "severity_raw": 0,
        "severity_label": "INFORMATIONAL",
        "title": finding.get("title", "Unknown finding"),
        "description": str(finding)[:500],
        "principal_arn": "",
        "source_ip": "",
        "resource_arn": "",
        "region": "",
        "account_id": "",
        "event_time": "",
        "raw_finding": finding,
    }


def extract_principal_from_guardduty(detail):
    """Extract principal ARN from GuardDuty finding detail."""
    resource = detail.get("resource", {})
    # Check accessKeyDetails
    access_key = resource.get("accessKeyDetails", {})
    if access_key.get("userArn"):
        return access_key["userArn"]
    # Check instanceDetails
    instance = resource.get("instanceDetails", {})
    if instance.get("iamInstanceProfile", {}).get("arn"):
        return instance["iamInstanceProfile"]["arn"]
    return ""


def extract_ip_from_guardduty(detail):
    """Extract source IP from GuardDuty finding."""
    service = detail.get("service", {})
    action = service.get("action", {})
    # Network connection action
    net_action = action.get("networkConnectionAction", {})
    if net_action.get("remoteIpDetails", {}).get("ipAddressV4"):
        return net_action["remoteIpDetails"]["ipAddressV4"]
    # AWS API call action
    api_action = action.get("awsApiCallAction", {})
    if api_action.get("remoteIpDetails", {}).get("ipAddressV4"):
        return api_action["remoteIpDetails"]["ipAddressV4"]
    return ""


def extract_resource_from_guardduty(detail):
    """Extract affected resource ARN from GuardDuty finding."""
    resource = detail.get("resource", {})
    if resource.get("resourceType") == "AccessKey":
        return resource.get("accessKeyDetails", {}).get("userArn", "")
    if resource.get("instanceDetails", {}).get("instanceId"):
        return f"arn:aws:ec2:::instance/{resource['instanceDetails']['instanceId']}"
    return ""


def severity_label_from_score(score):
    """Convert GuardDuty numeric severity to label."""
    if score >= 7.0:
        return "HIGH"
    elif score >= 4.0:
        return "MEDIUM"
    elif score >= 1.0:
        return "LOW"
    return "INFORMATIONAL"


def log_decision(finding_meta, severity, details, start_time):
    """Log the classification decision as structured JSON."""
    decision_record = {
        "timestamp": time.time(),
        "alert_id": finding_meta.get("finding_id", ""),
        "finding_type": finding_meta.get("finding_type", ""),
        "event_source": finding_meta.get("event_source", ""),
        "severity": severity,
        "principal_arn": finding_meta.get("principal_arn", ""),
        "source_ip": finding_meta.get("source_ip", ""),
        "resource_arn": finding_meta.get("resource_arn", ""),
        "mttd_seconds": round(time.time() - start_time, 2),
        "details": details,
    }
    # Log as structured JSON (picked up by CloudWatch Logs Insights)
    logger.info("DECISION: %s", json.dumps(decision_record, default=str))
