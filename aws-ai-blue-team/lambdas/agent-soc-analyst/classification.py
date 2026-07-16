"""
Classification Engine - Weighted scoring to determine P1-P4 severity.
"""
import logging

logger = logging.getLogger()

# Thresholds
P1_THRESHOLD = 70
P2_THRESHOLD = 45
P3_THRESHOLD = 20


def classify_finding(finding_meta, enrichment_context, matched_rules):
    """Classify a finding into P1-P4 based on weighted scoring.

    Returns: {"severity": "P1"|"P2"|"P3"|"P4", "score": int, "factors": [...]}
    """
    score = 0
    factors = []

    # Factor 1: Raw severity from source
    severity_raw = finding_meta.get("severity_raw", 0)
    severity_label = finding_meta.get("severity_label", "").upper()

    if severity_raw >= 8 or severity_label == "CRITICAL":
        score += 40
        factors.append({"factor": "source_severity_critical", "weight": 40})
    elif severity_raw >= 5 or severity_label == "HIGH":
        score += 30
        factors.append({"factor": "source_severity_high", "weight": 30})
    elif severity_raw >= 2 or severity_label == "MEDIUM":
        score += 20
        factors.append({"factor": "source_severity_medium", "weight": 20})
    else:
        score += 5
        factors.append({"factor": "source_severity_low", "weight": 5})

    # Factor 2: IP reputation
    ip_rep = enrichment_context.get("ip_reputation", {})
    abuse_score = ip_rep.get("abuse_confidence_score", 0)
    if abuse_score >= 80:
        score += 20
        factors.append({"factor": "ip_reputation_malicious", "weight": 20, "abuse_score": abuse_score})
    elif abuse_score >= 50:
        score += 15
        factors.append({"factor": "ip_reputation_suspicious", "weight": 15, "abuse_score": abuse_score})

    # Factor 3: Baseline deviation
    baseline = enrichment_context.get("baseline", {})
    if baseline.get("baseline_match") is False:
        score += 15
        factors.append({"factor": "baseline_deviation", "weight": 15, "deviation_type": baseline.get("deviation_type")})

    # Factor 4: IAM blast radius
    iam_ctx = enrichment_context.get("iam_context", {})
    if iam_ctx.get("has_admin"):
        score += 20
        factors.append({"factor": "principal_has_admin", "weight": 20})
    elif iam_ctx.get("policy_count", 0) > 5:
        score += 10
        factors.append({"factor": "principal_high_privilege", "weight": 10})

    # Factor 5: Detection rule matches
    for rule in matched_rules:
        weight = rule.get("classification_weight", 10)
        score += weight
        factors.append({"factor": f"detection_rule:{rule['id']}", "weight": weight})

    # Factor 6: Actor history anomaly
    actor = enrichment_context.get("actor_history", {})
    if actor.get("status") == "success" and actor.get("event_count", 0) == 0:
        # No prior activity = unusual
        score += 10
        factors.append({"factor": "no_prior_activity", "weight": 10})

    # Determine severity tier
    if score >= P1_THRESHOLD:
        severity = "P1"
    elif score >= P2_THRESHOLD:
        severity = "P2"
    elif score >= P3_THRESHOLD:
        severity = "P3"
    else:
        severity = "P4"

    result = {
        "severity": severity,
        "score": score,
        "factors": factors,
        "thresholds": {"P1": P1_THRESHOLD, "P2": P2_THRESHOLD, "P3": P3_THRESHOLD},
    }

    logger.info("Classification: %s (score=%d, factors=%d)", severity, score, len(factors))
    return result
