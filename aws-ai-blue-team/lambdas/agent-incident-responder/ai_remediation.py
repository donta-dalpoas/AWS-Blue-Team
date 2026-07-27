"""
AI-Powered Remediation Decisions - Uses Claude to select and explain actions.
"""
import json
import logging

from ai_engine import invoke_llm, parse_json_response

logger = logging.getLogger()


def get_ai_remediation_decision(finding, enrichment, remediation_type):
    """Ask Claude to validate/enhance the remediation decision.

    Returns: dict with reasoning, risk_assessment, and narrative
    """
    system_prompt = """You are an expert incident responder for AWS security. 
Your job is to validate remediation actions and provide clear reasoning.
Consider blast radius, production impact, and whether the action is proportional to the threat.
Always respond in valid JSON format."""

    user_message = f"""A security incident has been detected and I'm about to take remediation action.
Validate my decision and provide reasoning.

INCIDENT:
- Finding Type: {finding.get('finding_type', 'Unknown')}
- Severity: {finding.get('severity_raw', 'N/A')}/10
- Actor: {finding.get('principal_arn', 'N/A')}
- Source IP: {finding.get('source_ip', 'N/A')}
- Affected Resource: {finding.get('resource_arn', 'N/A')}

PROPOSED REMEDIATION: {remediation_type}
- cloudtrail_reenable: Re-enable CloudTrail logging
- s3_public_revert: Revert bucket policy and enable public access block
- iam_detach_disable: Detach admin policy and disable access keys
- sg_revoke: Revoke security group rule allowing 0.0.0.0/0

Respond with:
{{"approve": true/false, "reasoning": "Why this action is appropriate or not", "risk_assessment": "Low/Medium/High impact on production", "narrative": "A 2-3 sentence incident narrative for the forensic record"}}"""

    ai_response = invoke_llm(system_prompt, user_message)

    if ai_response.get("fallback"):
        return {
            "approve": True,
            "reasoning": "AI unavailable - proceeding with deterministic decision",
            "risk_assessment": "Unknown",
            "narrative": f"Automated remediation: {remediation_type} executed on {finding.get('resource_arn', 'unknown resource')}",
            "ai_source": "fallback",
        }

    parsed = parse_json_response(ai_response["response_text"])
    if parsed:
        parsed["ai_source"] = "claude"
        parsed["ai_tokens"] = ai_response["tokens_input"] + ai_response["tokens_output"]
        parsed["ai_latency_ms"] = ai_response["latency_ms"]
        return parsed

    return {
        "approve": True,
        "reasoning": ai_response["response_text"][:300],
        "risk_assessment": "Unknown",
        "narrative": f"Remediation: {remediation_type}",
        "ai_source": "parse_failed",
    }


def generate_incident_narrative(incident_id, finding, classification, remediation_result, mttr_seconds):
    """Use Claude to generate a human-quality incident narrative for GitHub issues."""
    system_prompt = """You are writing an incident report for a security team. 
Write a clear, concise 3-5 sentence narrative describing what happened, what was done, 
and the outcome. Use professional security operations language."""

    user_message = f"""Write an incident narrative for this security event:

Incident ID: {incident_id}
Finding: {finding.get('finding_type', 'Unknown')}
Severity: {classification.get('severity', 'Unknown')}
Actor: {finding.get('principal_arn', 'N/A')}
Source IP: {finding.get('source_ip', 'N/A')}
Resource: {finding.get('resource_arn', 'N/A')}
Action Taken: {remediation_result.get('action', 'N/A')}
MTTR: {mttr_seconds} seconds
Status: {remediation_result.get('status', 'completed')}

Write a professional narrative paragraph (no JSON, just plain text)."""

    ai_response = invoke_llm(system_prompt, user_message, max_tokens=300)

    if ai_response.get("fallback"):
        return f"Incident {incident_id}: {finding.get('finding_type')} detected. Automated remediation executed in {mttr_seconds}s."

    return ai_response["response_text"].strip()
