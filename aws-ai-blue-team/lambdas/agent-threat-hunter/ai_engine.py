"""
AI Engine - Shared module for AWS Bedrock (Claude) integration.
All agents import this to get LLM reasoning capabilities.
"""
import json
import logging
import time
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Configuration
AI_MODEL_ID = os.environ.get("AI_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
AI_ENABLED = os.environ.get("AI_ENABLED", "true").lower() == "true"
AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "1024"))
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.1"))
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Bedrock client (initialized on first use)
_bedrock_client = None


def get_bedrock_client():
    """Get or create the Bedrock Runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    return _bedrock_client


def invoke_llm(system_prompt, user_message, max_tokens=None, temperature=None):
    """Call AWS Bedrock Claude model and return structured response.

    Args:
        system_prompt: System-level instructions for the model
        user_message: The actual question/context to reason about
        max_tokens: Max output tokens (default from env)
        temperature: Randomness 0.0-1.0 (default from env)

    Returns:
        dict with keys: response_text, tokens_input, tokens_output, latency_ms, model, fallback
    """
    if not AI_ENABLED:
        logger.info("AI disabled - returning fallback")
        return _fallback_response("AI disabled via environment variable")

    max_tokens = max_tokens or AI_MAX_TOKENS
    temperature = temperature if temperature is not None else AI_TEMPERATURE

    # Construct the request body for Claude
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_message}
        ]
    }

    start_time = time.time()

    try:
        client = get_bedrock_client()
        response = client.invoke_model(
            modelId=AI_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body),
        )

        # Parse response
        response_body = json.loads(response["body"].read())
        response_text = response_body["content"][0]["text"]
        usage = response_body.get("usage", {})
        latency_ms = round((time.time() - start_time) * 1000, 2)

        result = {
            "response_text": response_text,
            "tokens_input": usage.get("input_tokens", 0),
            "tokens_output": usage.get("output_tokens", 0),
            "latency_ms": latency_ms,
            "model": AI_MODEL_ID,
            "fallback": False,
        }

        logger.info(
            "AI_CALL: model=%s, input_tokens=%d, output_tokens=%d, latency=%dms",
            AI_MODEL_ID, result["tokens_input"], result["tokens_output"], int(latency_ms),
        )

        return result

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("Bedrock API error (%s): %s", error_code, str(e))

        if error_code == "ThrottlingException":
            # Retry once after 2 seconds
            time.sleep(2)
            try:
                response = get_bedrock_client().invoke_model(
                    modelId=AI_MODEL_ID,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(request_body),
                )
                response_body = json.loads(response["body"].read())
                response_text = response_body["content"][0]["text"]
                usage = response_body.get("usage", {})
                latency_ms = round((time.time() - start_time) * 1000, 2)
                return {
                    "response_text": response_text,
                    "tokens_input": usage.get("input_tokens", 0),
                    "tokens_output": usage.get("output_tokens", 0),
                    "latency_ms": latency_ms,
                    "model": AI_MODEL_ID,
                    "fallback": False,
                }
            except Exception:
                pass

        return _fallback_response(f"Bedrock error: {error_code}")

    except Exception as e:
        logger.error("Unexpected AI error: %s", str(e))
        return _fallback_response(f"Unexpected error: {str(e)}")


def parse_json_response(response_text):
    """Extract JSON from LLM response text.

    The LLM may return JSON wrapped in markdown code blocks or with extra text.
    This function extracts the JSON portion.
    """
    text = response_text.strip()

    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    # Try finding JSON object in text
    for i, char in enumerate(text):
        if char == "{":
            # Find matching closing brace
            depth = 0
            for j in range(i, len(text)):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[i:j+1])
                        except json.JSONDecodeError:
                            break
            break

    logger.warning("Could not parse JSON from LLM response: %s", text[:200])
    return None


def _fallback_response(reason):
    """Return a fallback response when AI is unavailable."""
    return {
        "response_text": "",
        "tokens_input": 0,
        "tokens_output": 0,
        "latency_ms": 0,
        "model": "fallback",
        "fallback": True,
        "fallback_reason": reason,
    }
