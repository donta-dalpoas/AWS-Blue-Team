"""
Log Ingestor Lambda - S3 -> SQS -> OpenSearch
Processes security log files from S3 and indexes them into OpenSearch.
"""
import gzip
import json
import os
import logging
import time
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
INDEX_PREFIX = os.environ.get("OPENSEARCH_INDEX_PREFIX", "security-logs")
REGION = os.environ.get("OPENSEARCH_REGION", "us-east-1")
AUTH_TYPE = os.environ.get("OPENSEARCH_AUTH_TYPE", "iam")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "500"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))

s3_client = boto3.client("s3")


def lambda_handler(event, context):
    """Process SQS messages containing S3 event notifications."""
    batch_item_failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            # Handle SNS-wrapped messages or direct S3 events
            if "Records" in body:
                s3_records = body["Records"]
            elif "Message" in body:
                s3_records = json.loads(body["Message"]).get("Records", [])
            else:
                logger.warning("Unexpected message format: %s", message_id)
                continue

            for s3_record in s3_records:
                process_s3_event(s3_record)

        except Exception as e:
            logger.error("Failed to process message %s: %s", message_id, str(e))
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}


def process_s3_event(s3_record):
    """Download S3 object, parse, normalize, and index to OpenSearch."""
    bucket = s3_record["s3"]["bucket"]["name"]
    key = unquote_plus(s3_record["s3"]["object"]["key"])

    logger.info("Processing s3://%s/%s", bucket, key)

    # Determine source type from key prefix
    source_type = determine_source_type(key)
    if not source_type:
        logger.warning("Unknown source type for key: %s", key)
        return

    # Download and decompress
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        raw_data = response["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning("Object not found (deleted?): s3://%s/%s", bucket, key)
            return
        raise

    # Decompress if gzipped
    if key.endswith(".gz") or key.endswith(".gzip"):
        try:
            raw_data = gzip.decompress(raw_data)
        except Exception as e:
            logger.error("Gzip decompression failed for %s: %s", key, str(e))
            return

    # Parse and normalize
    documents = parse_log_data(raw_data, source_type, key)

    if documents:
        logger.info("Parsed %d documents from %s (%s)", len(documents), key, source_type)
        # In production, bulk index to OpenSearch here
        # For now, log success (OpenSearch bulk API integration would go here)
        index_documents(documents, source_type)


def determine_source_type(key):
    """Determine log source type from S3 key prefix."""
    if key.startswith("cloudtrail/"):
        return "cloudtrail"
    elif key.startswith("vpc-flow-logs/"):
        return "vpcflow"
    elif key.startswith("guardduty/"):
        return "guardduty"
    elif key.startswith("securityhub/"):
        return "securityhub"
    return None


def parse_log_data(raw_data, source_type, key):
    """Parse raw log data into normalized documents."""
    try:
        if source_type == "cloudtrail":
            return parse_cloudtrail(raw_data)
        elif source_type == "vpcflow":
            return parse_vpcflow(raw_data)
        elif source_type == "guardduty":
            return parse_guardduty(raw_data)
        elif source_type == "securityhub":
            return parse_securityhub(raw_data)
    except Exception as e:
        logger.error("Parse error for %s (%s): %s", key, source_type, str(e))
    return []


def parse_cloudtrail(raw_data):
    """Parse CloudTrail JSON records."""
    data = json.loads(raw_data)
    records = data.get("Records", [])
    documents = []

    for record in records:
        user_identity = record.get("userIdentity", {})
        doc = {
            "@timestamp": record.get("eventTime"),
            "event_source": record.get("eventSource", ""),
            "event_type": record.get("eventType", ""),
            "event_name": record.get("eventName", ""),
            "source_ip": record.get("sourceIPAddress", ""),
            "principal_arn": user_identity.get("arn", ""),
            "principal_name": user_identity.get("userName", user_identity.get("type", "")),
            "account_id": record.get("recipientAccountId", ""),
            "region": record.get("awsRegion", ""),
            "action": record.get("eventName", ""),
            "error_code": record.get("errorCode"),
            "user_agent": record.get("userAgent", ""),
            "action_result": "failure" if record.get("errorCode") else "success",
        }
        documents.append(doc)

    return documents


def parse_vpcflow(raw_data):
    """Parse VPC Flow Log records (space-delimited text)."""
    documents = []
    lines = raw_data.decode("utf-8", errors="replace").strip().split("\n")

    # Skip header if present
    start = 1 if lines and lines[0].startswith("version") else 0

    for line in lines[start:]:
        fields = line.split(" ")
        if len(fields) < 14:
            continue

        doc = {
            "@timestamp": datetime.fromtimestamp(int(fields[10]), tz=timezone.utc).isoformat()
            if fields[10].isdigit()
            else None,
            "event_source": "vpc-flow-logs",
            "source_ip": fields[3] if fields[3] != "-" else None,
            "destination_ip": fields[4] if fields[4] != "-" else None,
            "source_port": int(fields[5]) if fields[5].isdigit() else None,
            "destination_port": int(fields[6]) if fields[6].isdigit() else None,
            "protocol": fields[7],
            "packets": int(fields[8]) if fields[8].isdigit() else 0,
            "bytes_transferred": int(fields[9]) if fields[9].isdigit() else 0,
            "action_result": fields[12].lower() if len(fields) > 12 else "",
            "vpc_id": fields[14] if len(fields) > 14 else "",
        }
        documents.append(doc)

    return documents


def parse_guardduty(raw_data):
    """Parse GuardDuty finding JSON."""
    data = json.loads(raw_data)
    # GuardDuty exports can be a single finding or array
    findings = data if isinstance(data, list) else [data]
    documents = []

    for finding in findings:
        doc = {
            "@timestamp": finding.get("updatedAt", finding.get("createdAt")),
            "event_source": "guardduty",
            "finding_id": finding.get("id", ""),
            "finding_type": finding.get("type", ""),
            "severity": finding.get("severity", 0),
            "severity_score": float(finding.get("severity", 0)),
            "title": finding.get("title", ""),
            "description": finding.get("description", ""),
            "region": finding.get("region", ""),
            "account_id": finding.get("accountId", ""),
        }
        documents.append(doc)

    return documents


def parse_securityhub(raw_data):
    """Parse SecurityHub ASFF finding JSON."""
    data = json.loads(raw_data)
    findings = data.get("findings", [data]) if isinstance(data, dict) else [data]
    documents = []

    for finding in findings:
        severity = finding.get("Severity", {})
        doc = {
            "@timestamp": finding.get("UpdatedAt", finding.get("CreatedAt")),
            "event_source": "securityhub",
            "finding_id": finding.get("Id", ""),
            "finding_type": ",".join(finding.get("Types", [])),
            "severity": severity.get("Label", "INFORMATIONAL"),
            "severity_score": float(severity.get("Normalized", 0)) / 100.0,
            "title": finding.get("Title", ""),
            "description": finding.get("Description", ""),
            "resource_arn": (
                finding.get("Resources", [{}])[0].get("Id", "")
                if finding.get("Resources")
                else ""
            ),
            "action_result": finding.get("Compliance", {}).get("Status", ""),
        }
        documents.append(doc)

    return documents


def index_documents(documents, source_type):
    """Index documents to OpenSearch via bulk API.
    
    NOTE: Full OpenSearch bulk API implementation requires the
    opensearch-py library with AWS SigV4 signing. This is a
    placeholder that logs the indexing action.
    """
    today = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    index_name = f"{INDEX_PREFIX}-{source_type}-{today}"

    logger.info(
        "Would index %d documents to %s (OpenSearch: %s)",
        len(documents),
        index_name,
        OPENSEARCH_ENDPOINT,
    )
    # TODO: Implement actual OpenSearch bulk API call with:
    # - opensearchpy.OpenSearch client with AWS SigV4 auth
    # - Bulk API batching (BATCH_SIZE per request)
    # - Retry logic with exponential backoff for 429/5xx
    # - Partial batch failure reporting
