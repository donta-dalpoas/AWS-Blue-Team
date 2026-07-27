"""
AI-Powered Hypothesis Generation for Threat Hunter.
"""
import json
import logging

from ai_engine import invoke_llm, parse_json_response

logger = logging.getLogger()


def generate_ai_hypotheses(recent_alerts_summary):
    """Use Claude to generate hunting hypotheses based on recent alert patterns."""
    system_prompt = """You are an expert threat hunter working in AWS. Generate hunting hypotheses 
based on recent alert patterns. Each hypothesis should include a specific OpenSearch query 
that could validate it. Focus on threats that might evade rule-based detection.
Always respond in valid JSON format."""

    user_message = f"""Based on these recent alert patterns from the last 24 hours, generate 3 hunting hypotheses.

RECENT ACTIVITY SUMMARY:
{json.dumps(recent_alerts_summary, indent=2, default=str)}

For each hypothesis, provide:
1. A name describing what you're hunting for
2. Why this is suspicious (reasoning)
3. An OpenSearch DSL query to investigate

Respond with:
{{"hypotheses": [{{"name": "...", "reasoning": "...", "opensearch_query": {{"query": {{"bool": {{"must": [...]}}}}}}, "confidence_threshold": 0.7}}]}}"""

    ai_response = invoke_llm(system_prompt, user_message)

    if ai_response.get("fallback"):
        return None  # Caller will use static hypotheses

    parsed = parse_json_response(ai_response["response_text"])
    if parsed and "hypotheses" in parsed:
        logger.info("AI generated %d hypotheses", len(parsed["hypotheses"]))
        return parsed["hypotheses"]

    return None
