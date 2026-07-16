"""
Configuration loader - reads environment variables.
"""
import os


class Config:
    """Application configuration from environment variables."""

    def __init__(self):
        self.gateway_url = os.environ.get("AGENTCORE_GATEWAY_URL", "")
        self.opensearch_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
        self.baseline_bucket = os.environ.get("BASELINE_BUCKET", "")
        self.baseline_key = os.environ.get("BASELINE_KEY", "baselines/latest/baseline.json")
        self.sns_alert_topic_arn = os.environ.get("SNS_ALERT_TOPIC_ARN", "")
        self.environment = os.environ.get("ENVIRONMENT", "dev")
        self.slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
        self.ir_agent_function_name = os.environ.get("IR_AGENT_FUNCTION_NAME", "agent-incident-responder")


# Singleton
_config = None


def get_config():
    global _config
    if _config is None:
        _config = Config()
    return _config
