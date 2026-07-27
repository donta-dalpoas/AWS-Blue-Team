"""
AI-Powered Compliance Analysis.
"""
import json
import logging

from ai_engine import invoke_llm, parse_json_response

logger = logging.getLogger()


def rank_violations_with_ai(violations):
    """Use Claude to rank violations by risk and provide explanations."""
    if not violations:
        return violations

    system_prompt = """You are a cloud security compliance expert. Rank security violations 
by their risk to the organization and explain why each matters. Consider data exposure, 
blast radius, and exploitability. Respond in valid JSON format."""

    violations_summary = [
        {"type": v.get("violation_type"), "resource": v.get("resource"), "description": v.get("description")}
        for v in violations[:10]  # Limit to 10 to stay within token limits
    ]

    user_message = f"""Rank these AWS security violations by risk (highest risk first) and explain each:

VIOLATIONS:
{json.dumps(violations_summary, indent=2)}

Respond with:
{{"ranked_violations": [{{"violation_type": "...", "risk_score": 1-10, "explanation": "Why this is dangerous", "priority": "immediate|high|medium|low"}}]}}"""

    ai_response = invoke_llm(system_prompt, user_message)

    if ai_response.get("fallback"):
        return None  # Caller uses original order

    parsed = parse_json_response(ai_response["response_text"])
    if parsed and "ranked_violations" in parsed:
        logger.info("AI ranked %d violations", len(parsed["ranked_violations"]))
        return parsed["ranked_violations"]

    return None
