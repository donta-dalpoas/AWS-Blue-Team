"""
Enrichment Tools - Adds context to security findings.
4 tools: CloudTrail history, IP reputation, baseline check, IAM context.
"""
import json
import logging
import time
import boto3
from botocore.exceptions import ClientError

from cache import get_cached, set_cached
from config import get_config

logger = logging.getLogger()

cloudtrail_client = boto3.client("cloudtrail")
iam_client = boto3.client("iam")
s3_client = boto3.client("s3")

# Baseline loaded once at cold start
_baseline_cache = {"data": None, "loaded_at": 0}


def enrich_finding(finding_meta):
    """Run all 4 enrichment tools and return assembled context."""
    context = {}

    # Tool 1: CloudTrail actor history
    context["actor_history"] = query_cloudtrail(finding_meta.get("principal_arn", ""))

    # Tool 2: IP reputation
    context["ip_reputation"] = check_ip_reputation(finding_meta.get("source_ip", ""))

    # Tool 3: Baseline deviation
    context["baseline"] = check_baseline(
        finding_meta.get("principal_arn", ""),
        finding_meta.get("finding_type", ""),
    )

    # Tool 4: IAM context
    context["iam_context"] = get_iam_context(finding_meta.get("principal_arn", ""))

    return context


def query_cloudtrail(principal_arn):
    """Query CloudTrail for the principal's last 24h of API activity."""
    if not principal_arn:
        return {"status": "skipped", "reason": "no_principal_arn"}

    # Check cache
    cache_key = f"cloudtrail:{principal_arn}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        # Look up events for this user in the last 24 hours
        response = cloudtrail_client.lookup_events(
            LookupAttributes=[
                {"AttributeKey": "Username", "AttributeValue": principal_arn.split("/")[-1]}
            ],
            MaxResults=50,
        )

        events = []
        for event in response.get("Events", []):
            events.append({
                "event_name": event.get("EventName", ""),
                "event_time": event.get("EventTime", "").isoformat() if event.get("EventTime") else "",
                "event_source": event.get("EventSource", ""),
                "source_ip": event.get("CloudTrailEvent", "{}"),
            })

        result = {
            "status": "success",
            "event_count": len(events),
            "events": events[:20],  # Top 20 most recent
            "unique_services": list(set(e["event_source"] for e in events if e["event_source"])),
        }

        set_cached(cache_key, result)
        return result

    except ClientError as e:
        logger.warning("CloudTrail lookup failed for %s: %s", principal_arn, str(e))
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.warning("CloudTrail unexpected error: %s", str(e))
        return {"status": "error", "reason": str(e)}


def check_ip_reputation(ip_address):
    """Check IP reputation via AbuseIPDB (or mock for dev)."""
    if not ip_address:
        return {"status": "skipped", "reason": "no_ip_address"}

    # Skip internal/private IPs
    import ipaddress as iplib
    try:
        ip = iplib.ip_address(ip_address)
        if ip.is_private or ip.is_loopback or ip.is_reserved:
            return {"status": "skipped", "reason": "internal_ip", "ip": ip_address}
    except ValueError:
        return {"status": "skipped", "reason": "invalid_ip"}

    # Check cache
    cache_key = f"ip:{ip_address}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # For dev/MVP: return a simulated score based on IP characteristics
    # In production, replace with actual AbuseIPDB API call
    result = {
        "status": "success",
        "ip": ip_address,
        "abuse_confidence_score": 0,  # Default: unknown
        "total_reports": 0,
        "country": "unknown",
        "isp": "unknown",
        "note": "Using mock IP reputation - configure ABUSEIPDB_API_KEY for production",
    }

    # TODO: Production implementation:
    # import urllib.request
    # req = urllib.request.Request(
    #     f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip_address}&maxAgeInDays=90",
    #     headers={"Key": api_key, "Accept": "application/json"}
    # )
    # resp = urllib.request.urlopen(req, timeout=3)
    # data = json.loads(resp.read())["data"]
    # result = {"abuse_confidence_score": data["abuseConfidenceScore"], ...}

    set_cached(cache_key, result)
    return result


def check_baseline(principal_arn, finding_type):
    """Check if the entity/action is in the known-good baseline."""
    if not principal_arn:
        return {"status": "skipped", "reason": "no_principal_arn"}

    # Check cache
    cache_key = f"baseline:{principal_arn}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # Load baseline from S3
    baseline = _load_baseline()
    if not baseline:
        return {"status": "unavailable", "reason": "baseline_not_loaded"}

    # Check if principal exists in baseline
    baseline_users = [u.get("arn", "") for u in baseline.get("iam_users", [])]
    baseline_roles = [r.get("arn", "") for r in baseline.get("iam_roles", [])]
    all_known_principals = baseline_users + baseline_roles

    is_known = principal_arn in all_known_principals

    result = {
        "status": "success",
        "baseline_match": is_known,
        "deviation_type": "none" if is_known else "new_principal",
        "total_known_principals": len(all_known_principals),
    }

    set_cached(cache_key, result)
    return result


def get_iam_context(principal_arn):
    """Get IAM permission scope for the involved principal."""
    if not principal_arn:
        return {"status": "skipped", "reason": "no_principal_arn"}

    # Check cache
    cache_key = f"iam:{principal_arn}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        # Determine if user or role from ARN
        if ":user/" in principal_arn:
            username = principal_arn.split("/")[-1]
            return _get_user_context(username)
        elif ":role/" in principal_arn:
            role_name = principal_arn.split("/")[-1]
            return _get_role_context(role_name)
        else:
            return {"status": "skipped", "reason": "unsupported_principal_type"}

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            return {"status": "not_found", "reason": "principal_does_not_exist"}
        logger.warning("IAM context error for %s: %s", principal_arn, str(e))
        return {"status": "error", "reason": str(e)}


def _get_user_context(username):
    """Get IAM context for a user."""
    attached = iam_client.list_attached_user_policies(UserName=username)
    policies = [p["PolicyArn"] for p in attached.get("AttachedPolicies", [])]

    groups = iam_client.list_groups_for_user(UserName=username)
    group_names = [g["GroupName"] for g in groups.get("Groups", [])]

    has_admin = any("AdministratorAccess" in p for p in policies)

    result = {
        "status": "success",
        "principal_type": "user",
        "username": username,
        "attached_policies": policies,
        "has_admin": has_admin,
        "groups": group_names,
        "policy_count": len(policies),
    }

    set_cached(f"iam:arn:aws:iam::*:user/{username}", result)
    return result


def _get_role_context(role_name):
    """Get IAM context for a role."""
    attached = iam_client.list_attached_role_policies(RoleName=role_name)
    policies = [p["PolicyArn"] for p in attached.get("AttachedPolicies", [])]

    has_admin = any("AdministratorAccess" in p for p in policies)

    result = {
        "status": "success",
        "principal_type": "role",
        "role_name": role_name,
        "attached_policies": policies,
        "has_admin": has_admin,
        "policy_count": len(policies),
    }

    set_cached(f"iam:arn:aws:iam::*:role/{role_name}", result)
    return result


def _load_baseline():
    """Load the baseline snapshot from S3 (cached for 5 min)."""
    global _baseline_cache

    now = time.time()
    if _baseline_cache["data"] and (now - _baseline_cache["loaded_at"]) < 300:
        return _baseline_cache["data"]

    config = get_config()
    try:
        response = s3_client.get_object(
            Bucket=config.baseline_bucket,
            Key=config.baseline_key,
        )
        data = json.loads(response["Body"].read())
        _baseline_cache = {"data": data, "loaded_at": now}
        logger.info("Baseline loaded: %d users, %d roles",
                    len(data.get("iam_users", [])), len(data.get("iam_roles", [])))
        return data
    except ClientError as e:
        logger.warning("Failed to load baseline from S3: %s", str(e))
        return None
