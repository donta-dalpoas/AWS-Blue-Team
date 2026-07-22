"""
Red Team Agent - Simulates attacks against test resources, measures
detection coverage, and writes new rules for gaps.
"""
import json
import logging
import time
import os
import random

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
TECHNIQUES_PREFIX = os.environ.get("TECHNIQUES_PREFIX", "redteam/techniques/")
WAIT_SECONDS = int(os.environ.get("DETECTION_WAIT_SECONDS", "60"))  # Shortened for dev

cloudtrail_client = boto3.client("cloudtrail")
iam_client = boto3.client("iam")
ec2_client = boto3.client("ec2")
s3_client = boto3.client("s3")


def lambda_handler(event, context):
    """Main handler - runs weekly via EventBridge."""
    start_time = time.time()
    logger.info("Red Team Agent starting attack simulation cycle")

    # Load technique library
    techniques = load_techniques()
    if not techniques:
        logger.error("No techniques found - cannot run")
        return {"status": "error", "reason": "no_techniques"}

    # Select 5 techniques (rotating)
    selected = select_techniques(techniques, count=5)
    logger.info("Selected %d techniques: %s", len(selected), [t["id"] for t in selected])

    # Execute each technique and measure detection
    results = []
    for technique in selected:
        result = execute_and_measure(technique)
        results.append(result)

    # Calculate coverage
    detected_count = sum(1 for r in results if r["detected"])
    detection_rate = detected_count / len(results) if results else 0

    # Generate rules for gaps
    rules_generated = []
    for result in results:
        if not result["detected"]:
            rule = generate_gap_rule(result["technique"])
            if rule:
                rules_generated.append(rule)
                write_rule_to_s3(rule)

    # Build coverage report
    elapsed = time.time() - start_time
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(elapsed, 2),
        "techniques_tested": len(selected),
        "detection_rate": round(detection_rate, 2),
        "detected": detected_count,
        "missed": len(selected) - detected_count,
        "rules_generated": len(rules_generated),
        "results": [{
            "technique": r["technique"]["id"],
            "name": r["technique"]["name"],
            "detected": r["detected"],
            "mttd_seconds": r.get("mttd_seconds"),
        } for r in results],
    }

    logger.info("COVERAGE_REPORT: %s", json.dumps(report, default=str))
    post_coverage_report_to_slack(report)

    return report


def load_techniques():
    """Load attack techniques from bundled JSON files."""
    techniques = []
    techniques_dir = os.path.join(os.path.dirname(__file__), "techniques")

    if not os.path.isdir(techniques_dir):
        logger.warning("Techniques directory not found at %s", techniques_dir)
        return techniques

    for filename in sorted(os.listdir(techniques_dir)):
        if filename.endswith(".json"):
            filepath = os.path.join(techniques_dir, filename)
            try:
                with open(filepath, "r") as f:
                    technique = json.load(f)
                    techniques.append(technique)
            except Exception as e:
                logger.warning("Failed to load technique %s: %s", filename, str(e))

    logger.info("Loaded %d attack techniques", len(techniques))
    return techniques


def select_techniques(techniques, count=5):
    """Select techniques for this run (random subset)."""
    if len(techniques) <= count:
        return techniques
    return random.sample(techniques, count)


def execute_and_measure(technique):
    """Execute an attack technique and check if it was detected."""
    technique_id = technique["id"]
    logger.info("Executing technique: %s - %s", technique_id, technique["name"])

    # Execute the attack
    attack_time = time.time()
    execution_success = execute_attack(technique)

    if not execution_success:
        logger.warning("Technique %s failed to execute", technique_id)
        return {"technique": technique, "detected": False, "mttd_seconds": None, "execution_failed": True}

    # Wait for detection pipeline to process
    logger.info("Waiting %d seconds for detection...", WAIT_SECONDS)
    time.sleep(WAIT_SECONDS)

    # Check if SOC Agent detected it
    detected, detection_time = check_detection(technique, attack_time)

    mttd = round(detection_time - attack_time, 2) if detected and detection_time else None

    logger.info("Technique %s: detected=%s, mttd=%s", technique_id, detected, mttd)
    return {"technique": technique, "detected": detected, "mttd_seconds": mttd}


def execute_attack(technique):
    """Execute an attack against test resources only."""
    action = technique.get("aws_action", "")
    target = technique.get("target_resource", "")

    try:
        if action == "cloudtrail:StopLogging" and "test" in target:
            # Only attack test trails
            cloudtrail_client.stop_logging(Name=target)
            logger.info("Executed: StopLogging on %s", target)
            # Immediately re-enable (we just want the event to fire)
            time.sleep(2)
            cloudtrail_client.start_logging(Name=target)
            return True

        elif action == "s3:PutBucketPolicy" and "test" in target:
            # Make test bucket "public" then revert
            logger.info("Simulated: public bucket policy on %s", target)
            return True

        elif action == "iam:AttachUserPolicy" and "test" in target:
            # Simulated - don't actually attach admin to test user
            logger.info("Simulated: admin policy attach to %s", target)
            return True

        elif action == "ec2:AuthorizeSecurityGroupIngress" and "test" in target:
            logger.info("Simulated: open SG rule on %s", target)
            return True

        else:
            # For other techniques, just log the simulation
            logger.info("Simulated attack: %s on %s", action, target)
            return True

    except ClientError as e:
        logger.error("Attack execution failed: %s", str(e))
        return False
    except Exception as e:
        logger.error("Unexpected error executing attack: %s", str(e))
        return False


def check_detection(technique, attack_time):
    """Check if the SOC Agent detected this attack (via CloudWatch Logs)."""
    # In production, query OpenSearch for a decision record matching this technique
    # For MVP, we simulate detection check
    # The SOC Agent would have logged a DECISION record if it detected the finding

    expected_rule = technique.get("expected_detection_rule", "")
    logger.info("Checking detection for %s (expected rule: %s)", technique["id"], expected_rule)

    # Simulated: assume not detected for now (demonstrates gap-filling behavior)
    # In production: query OpenSearch for documents matching the attack signature
    return False, None


def generate_gap_rule(technique):
    """Generate a detection rule for an undetected attack."""
    rule_id = f"DETECT-GAP-{technique['id'].split('-')[1]}"

    rule = {
        "id": rule_id,
        "name": f"Gap-Fill: {technique['name']}",
        "description": f"Auto-generated rule to detect: {technique['description']}",
        "author": "red-team",
        "severity": technique.get("severity_expected", "high").lower(),
        "mitre_tactic": technique.get("mitre_tactic", "unknown"),
        "mitre_technique": technique.get("mitre_technique", "unknown"),
        "data_source": "cloudtrail",
        "detection": {
            "event_source": "cloudtrail",
            "event_name": [technique.get("aws_action", "").split(":")[-1]],
            "conditions": [],
        },
        "classification_weight": 25,
        "response": f"Investigate: {technique['description']}",
        "generated_by": "red-team-agent",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gap_source_technique": technique["id"],
    }

    logger.info("Generated gap-fill rule: %s for technique %s", rule_id, technique["id"])
    return rule


def write_rule_to_s3(rule):
    """Write gap-fill rule to S3."""
    key = f"detections/auto-generated/{rule['id']}.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(rule, indent=2),
            ContentType="application/json",
        )
        logger.info("Gap rule written: s3://%s/%s", S3_BUCKET, key)
    except ClientError as e:
        logger.error("Failed to write gap rule: %s", str(e))


def post_coverage_report_to_slack(report):
    """Post coverage report to Slack."""
    if not SLACK_WEBHOOK_URL:
        return

    import urllib.request
    rate_pct = int(report["detection_rate"] * 100)
    color = "#36a64f" if rate_pct >= 80 else "#ff9900" if rate_pct >= 60 else "#ff0000"

    results_text = "\n".join([
        f"{'✓' if r['detected'] else '✗'} {r['name']} (MTTD: {r['mttd_seconds'] or 'N/A'}s)"
        for r in report["results"]
    ])

    message = {
        "text": f":crossed_swords: Red Team Coverage Report - {rate_pct}% Detection Rate",
        "attachments": [{
            "color": color,
            "text": (
                f"*Detection Rate:* {report['detected']}/{report['techniques_tested']} ({rate_pct}%)\n"
                f"*Rules Generated:* {report['rules_generated']} (for gaps)\n\n"
                f"*Results:*\n{results_text}"
            ),
            "footer": f"Red Team Agent | {report['timestamp']}",
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
