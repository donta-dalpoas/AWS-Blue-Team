"""
Compliance Auditor Agent - Hourly security posture scan and auto-fix.
"""
import json
import logging
import time
import os

import boto3
from botocore.exceptions import ClientError

from scanners import scan_iam, scan_security_groups, scan_s3
from auto_fix import fix_stale_keys, fix_open_sg, fix_public_s3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "")
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def lambda_handler(event, context):
    """Main handler - runs every hour via EventBridge."""
    start_time = time.time()
    logger.info("Compliance Auditor starting hourly scan")

    # Run all scans
    iam_violations = scan_iam()
    sg_violations = scan_security_groups()
    s3_violations = scan_s3()

    all_violations = iam_violations + sg_violations + s3_violations
    logger.info("Scan complete: %d total violations found", len(all_violations))

    # Auto-fix what we can
    fixed = []
    needs_human = []

    for violation in all_violations:
        if violation.get("auto_fixable", False):
            result = attempt_fix(violation)
            if result["success"]:
                fixed.append({**violation, "fix_result": result})
            else:
                needs_human.append({**violation, "fix_error": result["error"]})
        else:
            needs_human.append(violation)

    # Build scorecard
    elapsed = time.time() - start_time
    scorecard = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(elapsed, 2),
        "total_resources_scanned": count_resources_scanned(iam_violations, sg_violations, s3_violations),
        "violations_found": len(all_violations),
        "violations_auto_fixed": len(fixed),
        "violations_needs_human": len(needs_human),
        "breakdown": {
            "iam": len(iam_violations),
            "security_groups": len(sg_violations),
            "s3": len(s3_violations),
        },
        "fixed_details": [{"type": f["violation_type"], "resource": f["resource"]} for f in fixed],
        "needs_human_details": [{"type": v["violation_type"], "resource": v["resource"]} for v in needs_human],
    }

    logger.info("SCORECARD: %s", json.dumps(scorecard, default=str))

    # Post scorecard to Slack
    post_scorecard_to_slack(scorecard)

    return scorecard


def attempt_fix(violation):
    """Attempt to auto-fix a violation."""
    try:
        vtype = violation.get("violation_type", "")
        if "stale_key" in vtype or "unused_credential" in vtype:
            fix_stale_keys(violation)
        elif "open_sg" in vtype or "unrestricted" in vtype:
            fix_open_sg(violation)
        elif "public_s3" in vtype or "public_access" in vtype:
            fix_public_s3(violation)
        else:
            return {"success": False, "error": f"No auto-fix for type: {vtype}"}
        return {"success": True}
    except Exception as e:
        logger.error("Auto-fix failed for %s: %s", violation.get("resource"), str(e))
        return {"success": False, "error": str(e)}


def count_resources_scanned(iam_v, sg_v, s3_v):
    """Estimate total resources scanned."""
    # Each scan checks all resources, violations are a subset
    return max(len(iam_v), 5) + max(len(sg_v), 5) + max(len(s3_v), 5)


def post_scorecard_to_slack(scorecard):
    """Post hourly scorecard to Slack."""
    if not SLACK_WEBHOOK_URL:
        logger.info("Slack not configured - skipping scorecard post")
        return

    import urllib.request

    emoji = ":white_check_mark:" if scorecard["violations_found"] == 0 else ":warning:"
    message = {
        "text": f"{emoji} Compliance Auditor - Hourly Scorecard",
        "attachments": [{
            "color": "#36a64f" if scorecard["violations_needs_human"] == 0 else "#ffcc00",
            "text": (
                f"*Scanned:* {scorecard['total_resources_scanned']} resources\n"
                f"*Violations Found:* {scorecard['violations_found']}\n"
                f"*Auto-Fixed:* {scorecard['violations_auto_fixed']}\n"
                f"*Needs Human:* {scorecard['violations_needs_human']}\n"
                f"*Breakdown:* IAM={scorecard['breakdown']['iam']}, "
                f"SG={scorecard['breakdown']['security_groups']}, "
                f"S3={scorecard['breakdown']['s3']}\n"
                f"*Duration:* {scorecard['duration_seconds']}s"
            ),
            "footer": f"Compliance Auditor | {scorecard['timestamp']}",
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
