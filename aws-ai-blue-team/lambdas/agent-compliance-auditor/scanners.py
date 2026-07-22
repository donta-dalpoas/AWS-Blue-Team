"""
Compliance Scanners - IAM, Security Groups, S3.
"""
import logging
from datetime import datetime, timezone, timedelta

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
iam_client = boto3.client("iam")
ec2_client = boto3.client("ec2")
s3_client = boto3.client("s3")


def scan_iam():
    """Scan IAM for compliance violations."""
    violations = []
    now = datetime.now(timezone.utc)

    try:
        paginator = iam_client.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page["Users"]:
                username = user["UserName"]

                # Check MFA
                mfa = iam_client.list_mfa_devices(UserName=username)
                if not mfa["MFADevices"]:
                    violations.append({
                        "violation_type": "no_mfa",
                        "resource": f"iam:user/{username}",
                        "description": f"User {username} has no MFA enabled",
                        "severity": "high",
                        "auto_fixable": False,
                    })

                # Check access keys
                keys = iam_client.list_access_keys(UserName=username)
                for key in keys.get("AccessKeyMetadata", []):
                    if key["Status"] != "Active":
                        continue
                    key_age = (now - key["CreateDate"].replace(tzinfo=timezone.utc)).days
                    if key_age > 90:
                        violations.append({
                            "violation_type": "stale_key",
                            "resource": f"iam:user/{username}/key/{key['AccessKeyId']}",
                            "description": f"Access key {key['AccessKeyId']} is {key_age} days old (>90)",
                            "severity": "medium",
                            "auto_fixable": True,
                            "fix_params": {"username": username, "key_id": key["AccessKeyId"]},
                        })

                    # Check last used
                    try:
                        last_used = iam_client.get_access_key_last_used(AccessKeyId=key["AccessKeyId"])
                        lu_date = last_used.get("AccessKeyLastUsed", {}).get("LastUsedDate")
                        if lu_date:
                            days_unused = (now - lu_date.replace(tzinfo=timezone.utc)).days
                            if days_unused > 60:
                                violations.append({
                                    "violation_type": "unused_credential",
                                    "resource": f"iam:user/{username}/key/{key['AccessKeyId']}",
                                    "description": f"Key unused for {days_unused} days (>60)",
                                    "severity": "medium",
                                    "auto_fixable": True,
                                    "fix_params": {"username": username, "key_id": key["AccessKeyId"]},
                                })
                    except ClientError:
                        pass

    except ClientError as e:
        logger.error("IAM scan error: %s", str(e))

    logger.info("IAM scan: %d violations found", len(violations))
    return violations


def scan_security_groups():
    """Scan security groups for unrestricted ingress on non-web ports."""
    violations = []

    try:
        paginator = ec2_client.get_paginator("describe_security_groups")
        for page in paginator.paginate():
            for sg in page["SecurityGroups"]:
                for rule in sg.get("IpPermissions", []):
                    for ip_range in rule.get("IpRanges", []):
                        if ip_range.get("CidrIp") == "0.0.0.0/0":
                            from_port = rule.get("FromPort", 0)
                            to_port = rule.get("ToPort", 0)
                            # Skip web ports
                            if from_port in (80, 443) and to_port in (80, 443):
                                continue
                            violations.append({
                                "violation_type": "open_sg_unrestricted",
                                "resource": f"ec2:sg/{sg['GroupId']}",
                                "description": f"SG {sg['GroupId']} allows 0.0.0.0/0 on port {from_port}-{to_port}",
                                "severity": "high",
                                "auto_fixable": True,
                                "fix_params": {
                                    "sg_id": sg["GroupId"],
                                    "protocol": rule.get("IpProtocol", "tcp"),
                                    "from_port": from_port,
                                    "to_port": to_port,
                                },
                            })
    except ClientError as e:
        logger.error("SG scan error: %s", str(e))

    logger.info("SG scan: %d violations found", len(violations))
    return violations


def scan_s3():
    """Scan S3 buckets for public access and missing encryption."""
    violations = []

    try:
        buckets = s3_client.list_buckets().get("Buckets", [])
        for bucket in buckets:
            bucket_name = bucket["Name"]

            # Check public access block
            try:
                pab = s3_client.get_public_access_block(Bucket=bucket_name)
                config = pab["PublicAccessBlockConfiguration"]
                if not all([
                    config.get("BlockPublicAcls", False),
                    config.get("IgnorePublicAcls", False),
                    config.get("BlockPublicPolicy", False),
                    config.get("RestrictPublicBuckets", False),
                ]):
                    violations.append({
                        "violation_type": "public_access_not_blocked",
                        "resource": f"s3:{bucket_name}",
                        "description": f"Bucket {bucket_name} does not have all public access blocks enabled",
                        "severity": "high",
                        "auto_fixable": True,
                        "fix_params": {"bucket_name": bucket_name},
                    })
            except ClientError as e:
                if "NoSuchPublicAccessBlockConfiguration" in str(e):
                    violations.append({
                        "violation_type": "public_access_not_blocked",
                        "resource": f"s3:{bucket_name}",
                        "description": f"Bucket {bucket_name} has no public access block configured",
                        "severity": "high",
                        "auto_fixable": True,
                        "fix_params": {"bucket_name": bucket_name},
                    })

            # Check encryption
            try:
                s3_client.get_bucket_encryption(Bucket=bucket_name)
            except ClientError as e:
                if "ServerSideEncryptionConfigurationNotFoundError" in str(e):
                    violations.append({
                        "violation_type": "no_encryption",
                        "resource": f"s3:{bucket_name}",
                        "description": f"Bucket {bucket_name} has no default encryption",
                        "severity": "medium",
                        "auto_fixable": False,
                    })

    except ClientError as e:
        logger.error("S3 scan error: %s", str(e))

    logger.info("S3 scan: %d violations found", len(violations))
    return violations
