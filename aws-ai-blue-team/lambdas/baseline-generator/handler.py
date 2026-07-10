"""
Baseline Generator Lambda - Weekly Posture Snapshot
Collects IAM users, IAM roles, security groups, S3 buckets, and GuardDuty
detector status. Writes a versioned JSON baseline to S3.
"""
import json
import os
import time
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# Configuration
BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
BASELINE_PREFIX = os.environ.get("BASELINE_PREFIX", "baselines/")
ACCOUNT_ID = os.environ.get("ACCOUNT_ID", "")
REGIONS = os.environ.get("REGIONS", "us-east-1").split(",")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GENERATOR_VERSION = "1.0.0"


def lambda_handler(event, context):
    """Main entry point."""
    start_time = time.time()
    logger.info("Starting baseline generation for account %s", ACCOUNT_ID)

    baseline = {
        "baseline_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_id": ACCOUNT_ID,
        "regions_scanned": REGIONS,
        "generator_version": GENERATOR_VERSION,
    }

    # Collect all resource categories
    baseline["iam_users"] = collect_iam_users()
    baseline["iam_roles"] = collect_iam_roles()
    baseline["security_groups"] = collect_security_groups(REGIONS)
    baseline["s3_buckets"] = collect_s3_buckets()
    baseline["guardduty_detectors"] = collect_guardduty_detectors(REGIONS)

    # Add metadata
    elapsed = time.time() - start_time
    baseline["execution_duration_seconds"] = round(elapsed, 2)
    baseline["resource_counts"] = {
        "iam_users": len(baseline["iam_users"]),
        "iam_roles": len(baseline["iam_roles"]),
        "security_groups": sum(len(v) for v in baseline["security_groups"].values()),
        "s3_buckets": len(baseline["s3_buckets"]),
        "guardduty_detectors": len(baseline["guardduty_detectors"]),
    }

    # Write to S3
    write_baseline_to_s3(baseline)

    logger.info(
        "Baseline generation complete in %.2f seconds. Counts: %s",
        elapsed,
        json.dumps(baseline["resource_counts"]),
    )

    return {"statusCode": 200, "body": json.dumps(baseline["resource_counts"])}


def collect_iam_users():
    """Collect all IAM users with policies and access keys."""
    iam = boto3.client("iam")
    users = []
    paginator = iam.get_paginator("list_users")

    for page in paginator.paginate():
        for user in page["Users"]:
            user_data = {
                "username": user["UserName"],
                "user_id": user["UserId"],
                "arn": user["Arn"],
                "create_date": user["CreateDate"].isoformat(),
                "password_last_used": (
                    user.get("PasswordLastUsed", "").isoformat()
                    if user.get("PasswordLastUsed")
                    else None
                ),
            }

            # MFA devices
            mfa_resp = iam.list_mfa_devices(UserName=user["UserName"])
            user_data["mfa_enabled"] = len(mfa_resp["MFADevices"]) > 0

            # Access keys
            keys_resp = iam.list_access_keys(UserName=user["UserName"])
            access_keys = []
            for key in keys_resp["AccessKeyMetadata"]:
                key_info = {
                    "access_key_id": key["AccessKeyId"][:8] + "...",  # Redact
                    "status": key["Status"],
                    "create_date": key["CreateDate"].isoformat(),
                }
                try:
                    last_used = iam.get_access_key_last_used(
                        AccessKeyId=key["AccessKeyId"]
                    )
                    lu = last_used.get("AccessKeyLastUsed", {})
                    key_info["last_used_date"] = (
                        lu["LastUsedDate"].isoformat()
                        if lu.get("LastUsedDate")
                        else None
                    )
                    key_info["last_used_region"] = lu.get("Region")
                    key_info["last_used_service"] = lu.get("ServiceName")
                except ClientError:
                    key_info["last_used_date"] = None
                access_keys.append(key_info)
            user_data["access_keys"] = access_keys

            # Attached policies
            attached = iam.list_attached_user_policies(UserName=user["UserName"])
            user_data["attached_policies"] = [
                p["PolicyArn"] for p in attached["AttachedPolicies"]
            ]

            # Inline policies
            inline = iam.list_user_policies(UserName=user["UserName"])
            user_data["inline_policies"] = inline["PolicyNames"]

            # Groups
            groups = iam.list_groups_for_user(UserName=user["UserName"])
            user_data["groups"] = [g["GroupName"] for g in groups["Groups"]]

            users.append(user_data)

    return users


def collect_iam_roles():
    """Collect all IAM roles with trust policies."""
    iam = boto3.client("iam")
    roles = []
    paginator = iam.get_paginator("list_roles")

    for page in paginator.paginate():
        for role in page["Roles"]:
            role_data = {
                "role_name": role["RoleName"],
                "role_id": role["RoleId"],
                "arn": role["Arn"],
                "create_date": role["CreateDate"].isoformat(),
                "trust_policy": role.get("AssumeRolePolicyDocument", {}),
                "max_session_duration": role.get("MaxSessionDuration", 3600),
                "permissions_boundary": (
                    role.get("PermissionsBoundary", {}).get("PermissionsBoundaryArn")
                ),
                "tags": {
                    t["Key"]: t["Value"] for t in role.get("Tags", [])
                },
            }

            # Attached policies
            attached = iam.list_attached_role_policies(RoleName=role["RoleName"])
            role_data["attached_policies"] = [
                p["PolicyArn"] for p in attached["AttachedPolicies"]
            ]

            # Inline policies
            inline = iam.list_role_policies(RoleName=role["RoleName"])
            role_data["inline_policies"] = inline["PolicyNames"]

            # Last used
            try:
                detail = iam.get_role(RoleName=role["RoleName"])
                last_used = detail["Role"].get("RoleLastUsed", {})
                role_data["last_used_date"] = (
                    last_used["LastUsedDate"].isoformat()
                    if last_used.get("LastUsedDate")
                    else None
                )
                role_data["last_used_region"] = last_used.get("Region")
            except ClientError:
                role_data["last_used_date"] = None
                role_data["last_used_region"] = None

            roles.append(role_data)

    return roles


def collect_security_groups(regions):
    """Collect security groups per region."""
    result = {}

    for region in regions:
        ec2 = boto3.client("ec2", region_name=region)
        sgs = []

        try:
            paginator = ec2.get_paginator("describe_security_groups")
            for page in paginator.paginate():
                for sg in page["SecurityGroups"]:
                    sg_data = {
                        "group_id": sg["GroupId"],
                        "group_name": sg["GroupName"],
                        "description": sg["Description"],
                        "vpc_id": sg.get("VpcId", ""),
                        "ingress_rules": [
                            {
                                "protocol": rule.get("IpProtocol", ""),
                                "from_port": rule.get("FromPort", -1),
                                "to_port": rule.get("ToPort", -1),
                                "cidr_blocks": [
                                    r["CidrIp"] for r in rule.get("IpRanges", [])
                                ],
                                "ipv6_cidr_blocks": [
                                    r["CidrIpv6"]
                                    for r in rule.get("Ipv6Ranges", [])
                                ],
                                "security_groups": [
                                    g["GroupId"]
                                    for g in rule.get("UserIdGroupPairs", [])
                                ],
                                "description": rule.get("IpRanges", [{}])[0].get(
                                    "Description", ""
                                )
                                if rule.get("IpRanges")
                                else "",
                            }
                            for rule in sg.get("IpPermissions", [])
                        ],
                        "egress_rules": [
                            {
                                "protocol": rule.get("IpProtocol", ""),
                                "from_port": rule.get("FromPort", -1),
                                "to_port": rule.get("ToPort", -1),
                                "cidr_blocks": [
                                    r["CidrIp"] for r in rule.get("IpRanges", [])
                                ],
                            }
                            for rule in sg.get("IpPermissionsEgress", [])
                        ],
                        "tags": {
                            t["Key"]: t["Value"] for t in sg.get("Tags", [])
                        },
                    }
                    sgs.append(sg_data)
        except ClientError as e:
            logger.warning("Error collecting SGs in %s: %s", region, str(e))

        result[region] = sgs

    return result


def collect_s3_buckets():
    """Collect S3 bucket configurations."""
    s3 = boto3.client("s3")
    buckets = []

    try:
        resp = s3.list_buckets()
    except ClientError as e:
        logger.error("Failed to list buckets: %s", str(e))
        return buckets

    for bucket in resp.get("Buckets", []):
        bucket_name = bucket["Name"]
        bucket_data = {
            "bucket_name": bucket_name,
            "creation_date": bucket["CreationDate"].isoformat(),
        }

        # Region
        try:
            loc = s3.get_bucket_location(Bucket=bucket_name)
            bucket_data["region"] = loc.get("LocationConstraint") or "us-east-1"
        except ClientError:
            bucket_data["region"] = "unknown"

        # Versioning
        try:
            ver = s3.get_bucket_versioning(Bucket=bucket_name)
            bucket_data["versioning"] = ver.get("Status", "Disabled")
        except ClientError:
            bucket_data["versioning"] = "Unknown"

        # Encryption
        try:
            enc = s3.get_bucket_encryption(Bucket=bucket_name)
            rules = enc["ServerSideEncryptionConfiguration"]["Rules"]
            sse = rules[0]["ApplyServerSideEncryptionByDefault"]
            bucket_data["encryption"] = {
                "sse_algorithm": sse.get("SSEAlgorithm", "None"),
                "kms_key_id": sse.get("KMSMasterKeyID"),
            }
        except ClientError:
            bucket_data["encryption"] = {"sse_algorithm": "None", "kms_key_id": None}

        # Public access block
        try:
            pab = s3.get_public_access_block(Bucket=bucket_name)
            config = pab["PublicAccessBlockConfiguration"]
            bucket_data["public_access_block"] = {
                "block_public_acls": config.get("BlockPublicAcls", False),
                "ignore_public_acls": config.get("IgnorePublicAcls", False),
                "block_public_policy": config.get("BlockPublicPolicy", False),
                "restrict_public_buckets": config.get("RestrictPublicBuckets", False),
            }
        except ClientError:
            bucket_data["public_access_block"] = None

        # Tags
        try:
            tags = s3.get_bucket_tagging(Bucket=bucket_name)
            bucket_data["tags"] = {
                t["Key"]: t["Value"] for t in tags.get("TagSet", [])
            }
        except ClientError:
            bucket_data["tags"] = {}

        buckets.append(bucket_data)

    return buckets


def collect_guardduty_detectors(regions):
    """Collect GuardDuty detector status per region."""
    result = {}

    for region in regions:
        gd = boto3.client("guardduty", region_name=region)
        try:
            detectors = gd.list_detectors()
            detector_ids = detectors.get("DetectorIds", [])
            if not detector_ids:
                result[region] = {"status": "NOT_ENABLED"}
                continue

            detector_id = detector_ids[0]
            detail = gd.get_detector(DetectorId=detector_id)
            result[region] = {
                "detector_id": detector_id,
                "status": detail.get("Status", "UNKNOWN"),
                "finding_publishing_frequency": detail.get(
                    "FindingPublishingFrequency", "UNKNOWN"
                ),
                "data_sources": {
                    "s3_logs": detail.get("DataSources", {})
                    .get("S3Logs", {})
                    .get("Status", "UNKNOWN"),
                    "kubernetes": detail.get("DataSources", {})
                    .get("Kubernetes", {})
                    .get("AuditLogs", {})
                    .get("Status", "UNKNOWN"),
                    "malware_protection": detail.get("DataSources", {})
                    .get("MalwareProtection", {})
                    .get("ScanEc2InstanceWithFindings", {})
                    .get("EbsVolumes", {})
                    .get("Status", "UNKNOWN"),
                },
            }
        except ClientError as e:
            logger.warning("GuardDuty error in %s: %s", region, str(e))
            result[region] = {"status": "ERROR", "error": str(e)}

    return result


def write_baseline_to_s3(baseline):
    """Write baseline JSON to S3 at dated and latest paths."""
    s3 = boto3.client("s3")
    now = datetime.now(timezone.utc)

    # Dated path
    dated_key = (
        f"{BASELINE_PREFIX}{now.year}/{now.month:02d}/{now.day:02d}/baseline.json"
    )
    # Latest path (overwritten each run)
    latest_key = f"{BASELINE_PREFIX}latest/baseline.json"

    body = json.dumps(baseline, indent=2, default=str)

    for key in [dated_key, latest_key]:
        try:
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=body,
                ContentType="application/json",
                ServerSideEncryption="aws:kms",
                Metadata={
                    "generator-version": GENERATOR_VERSION,
                    "account-id": ACCOUNT_ID,
                    "generated-at": now.isoformat(),
                },
            )
            logger.info("Wrote baseline to s3://%s/%s", BUCKET_NAME, key)
        except ClientError as e:
            logger.error("Failed to write baseline to %s: %s", key, str(e))
            raise
