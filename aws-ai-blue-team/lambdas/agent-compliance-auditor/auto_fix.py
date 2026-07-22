"""
Auto-Fix Actions for compliance violations.
"""
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
iam_client = boto3.client("iam")
ec2_client = boto3.client("ec2")
s3_client = boto3.client("s3")


def fix_stale_keys(violation):
    """Disable stale or unused access keys."""
    params = violation.get("fix_params", {})
    username = params.get("username")
    key_id = params.get("key_id")

    if not username or not key_id:
        raise ValueError("Missing username or key_id in fix_params")

    logger.info("Auto-fix: disabling key %s for user %s", key_id, username)
    iam_client.update_access_key(
        UserName=username,
        AccessKeyId=key_id,
        Status="Inactive",
    )
    logger.info("Key %s disabled successfully", key_id)


def fix_open_sg(violation):
    """Revoke unrestricted security group ingress rules."""
    params = violation.get("fix_params", {})
    sg_id = params.get("sg_id")
    protocol = params.get("protocol", "tcp")
    from_port = params.get("from_port")
    to_port = params.get("to_port")

    if not sg_id:
        raise ValueError("Missing sg_id in fix_params")

    logger.info("Auto-fix: revoking 0.0.0.0/0 on %s port %s-%s", sg_id, from_port, to_port)
    ec2_client.revoke_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            "IpProtocol": protocol,
            "FromPort": from_port,
            "ToPort": to_port,
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
        }],
    )
    logger.info("SG rule revoked on %s", sg_id)


def fix_public_s3(violation):
    """Enable all public access block settings on an S3 bucket."""
    params = violation.get("fix_params", {})
    bucket_name = params.get("bucket_name")

    if not bucket_name:
        raise ValueError("Missing bucket_name in fix_params")

    logger.info("Auto-fix: enabling public access block on %s", bucket_name)
    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    logger.info("Public access block enabled on %s", bucket_name)
