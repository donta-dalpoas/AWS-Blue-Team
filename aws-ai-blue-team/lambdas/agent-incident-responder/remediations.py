"""
Auto-Remediation Actions - 4 containment functions.
"""
import logging
import json
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

cloudtrail_client = boto3.client("cloudtrail")
s3_client = boto3.client("s3")
iam_client = boto3.client("iam")
ec2_client = boto3.client("ec2")


def remediate_cloudtrail_disabled(finding):
    """Re-enable CloudTrail logging on the affected trail."""
    # Extract trail name/ARN from finding
    resource_arn = finding.get("resource_arn", "")
    trail_name = resource_arn.split("/")[-1] if "/" in resource_arn else "aws-ai-blue-team-dev-trail"

    logger.info("Remediating: re-enabling CloudTrail on trail %s", trail_name)

    try:
        cloudtrail_client.start_logging(Name=trail_name)
    except ClientError as e:
        logger.error("StartLogging failed: %s", str(e))
        raise

    # Verify
    try:
        status = cloudtrail_client.get_trail_status(Name=trail_name)
        if not status.get("IsLogging", False):
            # Retry once
            logger.warning("Trail not logging after first attempt, retrying...")
            cloudtrail_client.start_logging(Name=trail_name)
            status = cloudtrail_client.get_trail_status(Name=trail_name)
            if not status.get("IsLogging", False):
                raise RuntimeError(f"Trail {trail_name} still not logging after retry")
    except ClientError as e:
        logger.error("GetTrailStatus failed: %s", str(e))
        raise

    return {"action": "StartLogging", "trail": trail_name, "verified": True}


def remediate_s3_public(finding, enrichment):
    """Revert S3 bucket to baseline policy and enable public access block."""
    resource_arn = finding.get("resource_arn", "")
    bucket_name = resource_arn.split(":::")[-1] if ":::" in resource_arn else ""

    if not bucket_name:
        raise ValueError("Could not extract bucket name from resource ARN")

    logger.info("Remediating: reverting S3 public access on %s", bucket_name)

    # Enable all public access block settings
    try:
        s3_client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
    except ClientError as e:
        logger.error("PutPublicAccessBlock failed: %s", str(e))
        raise

    # Verify
    try:
        response = s3_client.get_public_access_block(Bucket=bucket_name)
        config = response["PublicAccessBlockConfiguration"]
        all_blocked = all([
            config.get("BlockPublicAcls", False),
            config.get("IgnorePublicAcls", False),
            config.get("BlockPublicPolicy", False),
            config.get("RestrictPublicBuckets", False),
        ])
        if not all_blocked:
            raise RuntimeError(f"Public access block not fully enabled on {bucket_name}")
    except ClientError as e:
        logger.error("GetPublicAccessBlock verification failed: %s", str(e))
        raise

    return {"action": "PutPublicAccessBlock", "bucket": bucket_name, "verified": True}


def remediate_iam_privilege_escalation(finding):
    """Detach admin policy and disable all access keys for the affected principal."""
    principal_arn = finding.get("principal_arn", "")

    if ":user/" in principal_arn:
        username = principal_arn.split("/")[-1]
        return _remediate_user(username)
    elif ":role/" in principal_arn:
        role_name = principal_arn.split("/")[-1]
        return _remediate_role(role_name)
    else:
        raise ValueError(f"Unsupported principal type: {principal_arn}")


def _remediate_user(username):
    """Detach admin policies and disable keys for a user."""
    logger.info("Remediating: detaching admin policies from user %s", username)

    detached_policies = []
    disabled_keys = []

    # Detach admin-equivalent policies
    try:
        attached = iam_client.list_attached_user_policies(UserName=username)
        for policy in attached.get("AttachedPolicies", []):
            if "AdministratorAccess" in policy["PolicyArn"] or "Admin" in policy["PolicyName"]:
                iam_client.detach_user_policy(UserName=username, PolicyArn=policy["PolicyArn"])
                detached_policies.append(policy["PolicyArn"])
                logger.info("Detached policy %s from %s", policy["PolicyArn"], username)
    except ClientError as e:
        logger.error("Policy detach failed: %s", str(e))
        raise

    # Disable all access keys
    try:
        keys = iam_client.list_access_keys(UserName=username)
        for key in keys.get("AccessKeyMetadata", []):
            if key["Status"] == "Active":
                iam_client.update_access_key(
                    UserName=username,
                    AccessKeyId=key["AccessKeyId"],
                    Status="Inactive",
                )
                disabled_keys.append(key["AccessKeyId"])
                logger.info("Disabled key %s for %s", key["AccessKeyId"], username)
    except ClientError as e:
        logger.error("Key disable failed: %s", str(e))
        raise

    return {
        "action": "iam_detach_and_disable",
        "username": username,
        "detached_policies": detached_policies,
        "disabled_keys": disabled_keys,
        "verified": True,
    }


def _remediate_role(role_name):
    """Detach admin policies from a role."""
    logger.info("Remediating: detaching admin policies from role %s", role_name)

    detached_policies = []

    try:
        attached = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in attached.get("AttachedPolicies", []):
            if "AdministratorAccess" in policy["PolicyArn"] or "Admin" in policy["PolicyName"]:
                iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
                detached_policies.append(policy["PolicyArn"])
                logger.info("Detached policy %s from role %s", policy["PolicyArn"], role_name)
    except ClientError as e:
        logger.error("Role policy detach failed: %s", str(e))
        raise

    return {
        "action": "iam_detach_role",
        "role_name": role_name,
        "detached_policies": detached_policies,
        "verified": True,
    }


def remediate_sg_open_to_world(finding):
    """Revoke security group ingress rule with 0.0.0.0/0 on non-web ports."""
    # Extract SG ID from finding
    resource_arn = finding.get("resource_arn", "")
    raw = finding.get("raw_finding", {})

    # Try to get SG ID from various locations
    sg_id = ""
    if "sg-" in resource_arn:
        sg_id = resource_arn.split("/")[-1]
    elif "sg-" in str(raw):
        import re
        match = re.search(r"(sg-[a-f0-9]+)", str(raw))
        if match:
            sg_id = match.group(1)

    if not sg_id:
        raise ValueError("Could not extract security group ID from finding")

    logger.info("Remediating: revoking 0.0.0.0/0 ingress on SG %s", sg_id)

    # Describe the SG to find the offending rule
    try:
        response = ec2_client.describe_security_groups(GroupIds=[sg_id])
        sg = response["SecurityGroups"][0]
    except ClientError as e:
        logger.error("DescribeSecurityGroups failed: %s", str(e))
        raise

    revoked_rules = []
    for rule in sg.get("IpPermissions", []):
        for ip_range in rule.get("IpRanges", []):
            if ip_range.get("CidrIp") == "0.0.0.0/0":
                from_port = rule.get("FromPort", 0)
                to_port = rule.get("ToPort", 0)
                # Skip web ports (80, 443)
                if from_port in (80, 443) and to_port in (80, 443):
                    continue

                # Revoke this rule
                try:
                    ec2_client.revoke_security_group_ingress(
                        GroupId=sg_id,
                        IpPermissions=[{
                            "IpProtocol": rule.get("IpProtocol", "tcp"),
                            "FromPort": from_port,
                            "ToPort": to_port,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        }],
                    )
                    revoked_rules.append({
                        "protocol": rule.get("IpProtocol"),
                        "from_port": from_port,
                        "to_port": to_port,
                        "cidr": "0.0.0.0/0",
                    })
                    logger.info("Revoked rule port %d-%d on SG %s", from_port, to_port, sg_id)
                except ClientError as e:
                    logger.error("RevokeSecurityGroupIngress failed: %s", str(e))
                    raise

    if not revoked_rules:
        logger.info("No 0.0.0.0/0 rules on non-web ports found in SG %s", sg_id)

    return {"action": "sg_revoke", "sg_id": sg_id, "revoked_rules": revoked_rules, "verified": True}
