"""
Forensic Capture - Pre/post state snapshots to S3.
"""
import json
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
s3_client = boto3.client("s3")
cloudtrail_client = boto3.client("cloudtrail")
iam_client = boto3.client("iam")
ec2_client = boto3.client("ec2")


def capture_pre_state(incident_id, remediation_type, finding, bucket_name):
    """Capture resource state before remediation."""
    state = _get_resource_state(remediation_type, finding)
    state["captured_at"] = time.time()
    state["incident_id"] = incident_id
    state["phase"] = "pre"

    key = f"forensics/{incident_id}/pre/{remediation_type}.json"
    _write_to_s3(bucket_name, key, state)
    logger.info("Pre-state captured: s3://%s/%s", bucket_name, key)
    return state


def capture_post_state(incident_id, remediation_type, finding, bucket_name):
    """Capture resource state after remediation."""
    state = _get_resource_state(remediation_type, finding)
    state["captured_at"] = time.time()
    state["incident_id"] = incident_id
    state["phase"] = "post"

    key = f"forensics/{incident_id}/post/{remediation_type}.json"
    _write_to_s3(bucket_name, key, state)
    logger.info("Post-state captured: s3://%s/%s", bucket_name, key)
    return state


def _get_resource_state(remediation_type, finding):
    """Get current state of the affected resource."""
    try:
        if remediation_type == "cloudtrail_reenable":
            trail_name = finding.get("resource_arn", "").split("/")[-1] or "aws-ai-blue-team-dev-trail"
            status = cloudtrail_client.get_trail_status(Name=trail_name)
            return {"resource_type": "cloudtrail", "trail_name": trail_name, "is_logging": status.get("IsLogging", False)}

        elif remediation_type == "s3_public_revert":
            bucket = finding.get("resource_arn", "").split(":::")[-1]
            try:
                pab = s3_client.get_public_access_block(Bucket=bucket)
                config = pab["PublicAccessBlockConfiguration"]
            except ClientError:
                config = {"BlockPublicAcls": False, "IgnorePublicAcls": False, "BlockPublicPolicy": False, "RestrictPublicBuckets": False}
            return {"resource_type": "s3", "bucket": bucket, "public_access_block": config}

        elif remediation_type == "iam_detach_disable":
            principal_arn = finding.get("principal_arn", "")
            if ":user/" in principal_arn:
                username = principal_arn.split("/")[-1]
                policies = iam_client.list_attached_user_policies(UserName=username)
                keys = iam_client.list_access_keys(UserName=username)
                return {
                    "resource_type": "iam_user",
                    "username": username,
                    "attached_policies": [p["PolicyArn"] for p in policies.get("AttachedPolicies", [])],
                    "access_keys": [{"id": k["AccessKeyId"], "status": k["Status"]} for k in keys.get("AccessKeyMetadata", [])],
                }
            else:
                role_name = principal_arn.split("/")[-1]
                policies = iam_client.list_attached_role_policies(RoleName=role_name)
                return {
                    "resource_type": "iam_role",
                    "role_name": role_name,
                    "attached_policies": [p["PolicyArn"] for p in policies.get("AttachedPolicies", [])],
                }

        elif remediation_type == "sg_revoke":
            import re
            sg_id = ""
            resource_arn = finding.get("resource_arn", "")
            if "sg-" in resource_arn:
                sg_id = resource_arn.split("/")[-1]
            else:
                match = re.search(r"(sg-[a-f0-9]+)", str(finding))
                if match:
                    sg_id = match.group(1)
            if sg_id:
                response = ec2_client.describe_security_groups(GroupIds=[sg_id])
                sg = response["SecurityGroups"][0]
                return {"resource_type": "security_group", "sg_id": sg_id, "ingress_rules": sg.get("IpPermissions", [])}

    except Exception as e:
        logger.warning("Failed to capture state for %s: %s", remediation_type, str(e))

    return {"resource_type": remediation_type, "state": "capture_failed", "error": "Could not read resource state"}


def _write_to_s3(bucket, key, data):
    """Write JSON data to S3."""
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, indent=2, default=str),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
        )
    except ClientError as e:
        logger.error("Failed to write forensic data to S3: %s", str(e))
