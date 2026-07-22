"""
Threat Hunter Agent - Generates hunting hypotheses, queries OpenSearch,
and writes new detection rules for confirmed threats.
"""
import json
import logging
import time
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def lambda_handler(event, context):
    """Main handler - runs every 6 hours via EventBridge."""
    start_time = time.time()
    logger.info("Threat Hunter starting hunt cycle")

    # Generate hypotheses based on recent data
    hypotheses = generate_hypotheses()
    logger.info("Generated %d hypotheses", len(hypotheses))

    # Execute each hypothesis as an OpenSearch query
    results = []
    rules_generated = []

    for hypothesis in hypotheses:
        query_result = execute_hunt_query(hypothesis)
        results.append(query_result)

        # If high confidence hit, generate detection rule
        if query_result.get("hit_count", 0) > 0 and query_result.get("confidence", 0) >= 0.7:
            rule = generate_detection_rule(hypothesis, query_result)
            if rule:
                rules_generated.append(rule)
                write_rule_to_s3(rule)

    # Build hunt report
    elapsed = time.time() - start_time
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(elapsed, 2),
        "hypotheses_tested": len(hypotheses),
        "queries_executed": len(results),
        "hits_found": sum(1 for r in results if r.get("hit_count", 0) > 0),
        "rules_generated": len(rules_generated),
        "hypotheses": [h["name"] for h in hypotheses],
        "new_rules": [r["id"] for r in rules_generated],
    }

    logger.info("HUNT_REPORT: %s", json.dumps(report, default=str))
    post_hunt_report_to_slack(report)

    return report


def generate_hypotheses():
    """Generate hunting hypotheses based on common threat patterns."""
    # In production, these would be dynamically generated from recent alert data
    # For now, use a static set of common hunt hypotheses
    return [
        {
            "id": "HUNT-001",
            "name": "Unusual cross-account activity",
            "description": "Look for AssumeRole calls from accounts not seen in baseline",
            "query_type": "cloudtrail",
            "search_params": {
                "event_name": "AssumeRole",
                "time_range": "24h",
                "anomaly": "source_account_not_in_baseline",
            },
            "confidence_threshold": 0.7,
        },
        {
            "id": "HUNT-002",
            "name": "High-volume API calls from single principal",
            "description": "Principals making >100 API calls in 1 hour - possible automation abuse or recon",
            "query_type": "cloudtrail",
            "search_params": {
                "aggregation": "by_principal",
                "threshold": 100,
                "time_range": "1h",
            },
            "confidence_threshold": 0.6,
        },
        {
            "id": "HUNT-003",
            "name": "After-hours admin activity",
            "description": "Administrative actions between 00:00-06:00 UTC from human users",
            "query_type": "cloudtrail",
            "search_params": {
                "event_names": ["CreateUser", "AttachUserPolicy", "PutBucketPolicy"],
                "time_range": "24h",
                "hour_filter": "0-6",
            },
            "confidence_threshold": 0.8,
        },
        {
            "id": "HUNT-004",
            "name": "Data exfiltration indicators",
            "description": "Large S3 GetObject calls from unusual IPs or principals",
            "query_type": "cloudtrail",
            "search_params": {
                "event_name": "GetObject",
                "anomaly": "unusual_volume_or_source",
                "time_range": "24h",
            },
            "confidence_threshold": 0.7,
        },
        {
            "id": "HUNT-005",
            "name": "Privilege escalation chain",
            "description": "Sequence: CreateAccessKey -> AttachPolicy -> AssumeRole within 1 hour",
            "query_type": "cloudtrail",
            "search_params": {
                "event_sequence": ["CreateAccessKey", "AttachUserPolicy", "AssumeRole"],
                "time_window": "1h",
                "same_principal": True,
            },
            "confidence_threshold": 0.9,
        },
    ]


def execute_hunt_query(hypothesis):
    """Execute a hunt hypothesis as a query (simulated for MVP)."""
    # In production, this would build and execute an OpenSearch DSL query
    # For MVP, we simulate the query execution
    logger.info("Executing hunt: %s", hypothesis["name"])

    # Simulated result - in production, query OpenSearch
    result = {
        "hypothesis_id": hypothesis["id"],
        "hypothesis_name": hypothesis["name"],
        "hit_count": 0,  # Simulated: no hits in dev (no real attack data)
        "confidence": 0.0,
        "query_executed": True,
        "error": None,
    }

    logger.info("Hunt result for %s: %d hits, confidence=%.2f",
                hypothesis["name"], result["hit_count"], result["confidence"])
    return result


def generate_detection_rule(hypothesis, query_result):
    """Generate a new detection rule from a confirmed hunt finding."""
    rule_id = f"DETECT-AUTO-{hypothesis['id'].split('-')[1]}"

    rule = {
        "id": rule_id,
        "name": f"Auto-Generated: {hypothesis['name']}",
        "description": hypothesis["description"],
        "author": "threat-hunter",
        "severity": "high",
        "mitre_tactic": "discovery",
        "mitre_technique": "T1087",
        "data_source": "cloudtrail",
        "detection": {
            "event_source": "cloudtrail",
            "event_name": hypothesis.get("search_params", {}).get("event_names", []),
            "conditions": [],
        },
        "classification_weight": 20,
        "response": f"Investigate: {hypothesis['description']}",
        "generated_by": "threat-hunter-agent",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    logger.info("Generated detection rule: %s", rule_id)
    return rule


def write_rule_to_s3(rule):
    """Write auto-generated rule to S3 for review."""
    s3 = boto3.client("s3")
    key = f"detections/auto-generated/{rule['id']}.json"

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(rule, indent=2),
            ContentType="application/json",
        )
        logger.info("Rule written to s3://%s/%s", S3_BUCKET, key)
    except ClientError as e:
        logger.error("Failed to write rule to S3: %s", str(e))


def post_hunt_report_to_slack(report):
    """Post hunt report to Slack."""
    if not SLACK_WEBHOOK_URL:
        return

    import urllib.request
    message = {
        "text": ":mag: Threat Hunter - Hunt Report",
        "attachments": [{
            "color": "#36a64f" if report["hits_found"] == 0 else "#ff9900",
            "text": (
                f"*Hypotheses Tested:* {report['hypotheses_tested']}\n"
                f"*Hits Found:* {report['hits_found']}\n"
                f"*Rules Generated:* {report['rules_generated']}\n"
                f"*Duration:* {report['duration_seconds']}s"
            ),
            "footer": f"Threat Hunter | {report['timestamp']}",
        }]
    }

    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.error("Slack post failed: %s", str(e))
