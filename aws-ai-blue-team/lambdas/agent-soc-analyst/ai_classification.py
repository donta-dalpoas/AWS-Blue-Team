"""
AI-Powered Classification - Uses Claude to reason about findings.
Falls back to deterministic scoring if AI is unavailable.
"""
import json
import logging

from ai_engine import invoke_llm, parse_json_response

logger = logging.getLogger()


def classify_with_ai(finding_meta, enrichment_context, matched_rules, deterministic_result):
    """Use Claude to classify a finding with natural-language reasoning.

    Args:
        finding_meta: Parsed finding metadata
        enrichment_context: Results from all 4 enrichment tools
        matched_rules: Detection rules that matched this finding
        deterministic_result: The rule-based classification (fallback)

    Returns:
        dict with: severity, score, reasoning, recommended_actions, confidence, source
    """
    # Build the prompt
    system_prompt = """You are an expert SOC analyst working in an AWS security operations center. 
Your job is to analyze security findings and classify their severity. You have access to enrichment 
data including actor history, IP reputation, baseline comparisons, and IAM context.

Classify findings as:
- P1 (Critical): Active compromise, immediate threat, high blast radius
- P2 (High): Likely malicious, needs rapid response, significant risk
- P3 (Medium): Suspicious but uncertain, needs investigation
- P4 (Informational): Low risk, routine, or known-good activity

Always respond in valid JSON format."""

    # Build context for the LLM
    actor_history = enrichment_context.get("actor_history", {})
    ip_rep = enrichment_context.get("ip_reputation", {})
    baseline = enrichment_context.get("baseline", {})
    iam_ctx = enrichment_context.get("iam_context", {})

    user_message = f"""Analyze this security finding and classify its severity.

FINDING:
- Type: {finding_meta.get('finding_type', 'Unknown')}
- Source: {finding_meta.get('event_source', 'Unknown')} (raw severity: {finding_meta.get('severity_raw', 0)}/10)
- Title: {finding_meta.get('title', 'N/A')}
- Actor: {finding_meta.get('principal_arn', 'N/A')}
- Source IP: {finding_meta.get('source_ip', 'N/A')}
- Resource: {finding_meta.get('resource_arn', 'N/A')}
- Region: {finding_meta.get('region', 'N/A')}

ENRICHMENT CONTEXT:
- Actor History: {actor_history.get('event_count', 'N/A')} API calls in last 24h, services: {actor_history.get('unique_services', [])}
- IP Reputation: Abuse score {ip_rep.get('abuse_confidence_score', 'N/A')}/100, reports: {ip_rep.get('total_reports', 'N/A')}
- Baseline: Match={baseline.get('baseline_match', 'unknown')}, Deviation={baseline.get('deviation_type', 'none')}
- IAM Context: Type={iam_ctx.get('principal_type', 'N/A')}, Admin={iam_ctx.get('has_admin', 'N/A')}, Policies={iam_ctx.get('policy_count', 'N/A')}

DETECTION RULES MATCHED: {[r.get('id', '') + ': ' + r.get('name', '') for r in matched_rules] if matched_rules else 'None'}

DETERMINISTIC SCORE: {deterministic_result.get('severity', 'N/A')} (score: {deterministic_result.get('score', 0)})

Respond with this exact JSON structure:
{{"severity": "P1 or P2 or P3 or P4", "reasoning": "2-3 sentence explanation of why", "recommended_actions": ["action 1", "action 2"], "confidence": 0.0 to 1.0}}"""

    # Call the LLM
    ai_response = invoke_llm(system_prompt, user_message)

    # If fallback (AI unavailable), use deterministic
    if ai_response.get("fallback"):
        logger.info("AI unavailable - using deterministic classification")
        return {
            **deterministic_result,
            "ai_reasoning": None,
            "ai_confidence": None,
            "classification_source": "deterministic",
            "ai_fallback_reason": ai_response.get("fallback_reason"),
        }

    # Parse the LLM response
    parsed = parse_json_response(ai_response["response_text"])

    if parsed and "severity" in parsed:
        # Validate severity is valid
        severity = parsed["severity"].upper()
        if severity not in ("P1", "P2", "P3", "P4"):
            severity = deterministic_result["severity"]

        result = {
            "severity": severity,
            "score": deterministic_result["score"],  # Keep deterministic score for reference
            "factors": deterministic_result.get("factors", []),
            "ai_reasoning": parsed.get("reasoning", ""),
            "ai_recommended_actions": parsed.get("recommended_actions", []),
            "ai_confidence": parsed.get("confidence", 0.0),
            "ai_tokens_input": ai_response["tokens_input"],
            "ai_tokens_output": ai_response["tokens_output"],
            "ai_latency_ms": ai_response["latency_ms"],
            "ai_model": ai_response["model"],
            "classification_source": "ai",
        }

        logger.info(
            "AI Classification: %s (confidence=%.2f, deterministic=%s) - %s",
            severity, result["ai_confidence"], deterministic_result["severity"],
            result["ai_reasoning"][:100],
        )

        return result

    # If parsing failed, fall back to deterministic
    logger.warning("AI response parsing failed - using deterministic")
    return {
        **deterministic_result,
        "ai_reasoning": ai_response["response_text"][:500],
        "ai_confidence": None,
        "classification_source": "deterministic_fallback",
    }
