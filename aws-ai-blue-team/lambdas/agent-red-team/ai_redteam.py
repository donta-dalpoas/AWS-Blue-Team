"""
AI-Powered Attack Variation Suggestions for Red Team.
"""
import json
import logging

from ai_engine import invoke_llm, parse_json_response

logger = logging.getLogger()


def suggest_attack_variations(detected_techniques, missed_techniques, current_rules):
    """Use Claude to suggest novel attack variations that might bypass current detection."""
    system_prompt = """You are a red team operator testing AWS security detection capabilities. 
Suggest attack technique variations that might bypass existing detection rules. 
Focus on realistic AWS attack scenarios. Respond in valid JSON format."""

    user_message = f"""Our detection system caught these attacks but missed others. Suggest variations.

DETECTED (our rules caught these):
{json.dumps(detected_techniques, indent=2, default=str)}

MISSED (our rules did NOT catch these):
{json.dumps(missed_techniques, indent=2, default=str)}

CURRENT DETECTION RULES:
{json.dumps([r.get('name', '') for r in current_rules[:10]], indent=2)}

Suggest 3 attack variations that might bypass current detection:
{{"variations": [{{"name": "...", "description": "...", "why_it_bypasses": "...", "mitre_technique": "T1xxx", "suggested_detection": "How to detect this"}}]}}"""

    ai_response = invoke_llm(system_prompt, user_message)

    if ai_response.get("fallback"):
        return None  # Caller uses standard technique library

    parsed = parse_json_response(ai_response["response_text"])
    if parsed and "variations" in parsed:
        logger.info("AI suggested %d attack variations", len(parsed["variations"]))
        return parsed["variations"]

    return None
