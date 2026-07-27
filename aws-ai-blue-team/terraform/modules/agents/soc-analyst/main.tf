# =============================================================================
# SOC Analyst Agent Module
# =============================================================================
# Deploys the SOC Analyst Agent Lambda, subscribes it to the security findings
# SNS topic, and configures monitoring/alerting.
# =============================================================================

data "archive_file" "soc_analyst" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../lambdas/agent-soc-analyst"
  output_path = "${path.module}/agent-soc-analyst.zip"
}

# -----------------------------------------------------------------------------
# Lambda Function
# -----------------------------------------------------------------------------
resource "aws_lambda_function" "soc_analyst" {
  filename         = data.archive_file.soc_analyst.output_path
  function_name    = "agent-soc-analyst"
  role             = var.agent_role_arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.soc_analyst.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 1024
  timeout          = 30
  reserved_concurrent_executions = 20

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      AGENTCORE_GATEWAY_URL = var.gateway_url
      OPENSEARCH_ENDPOINT   = var.opensearch_endpoint
      BASELINE_BUCKET       = var.s3_bucket_name
      BASELINE_KEY          = "baselines/latest/baseline.json"
      SNS_ALERT_TOPIC_ARN   = var.sns_alert_topic_arn
      AI_MODEL_ID           = "anthropic.claude-3-haiku-20240307-v1:0"
      AI_ENABLED            = "true"
      ENVIRONMENT           = "dev"
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.soc_agent_dlq.arn
  }

  tags = {
    Name  = "${var.name_prefix}-agent-soc-analyst"
    Agent = "soc-analyst"
  }
}

# -----------------------------------------------------------------------------
# SNS Subscription - Security Findings -> SOC Agent
# -----------------------------------------------------------------------------
resource "aws_sns_topic_subscription" "soc_agent" {
  topic_arn = var.sns_topic_arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.soc_analyst.arn
}

resource "aws_lambda_permission" "allow_sns" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.soc_analyst.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = var.sns_topic_arn
}

# -----------------------------------------------------------------------------
# Dead-Letter Queue
# -----------------------------------------------------------------------------
resource "aws_sqs_queue" "soc_agent_dlq" {
  name                      = "${var.name_prefix}-soc-agent-dlq"
  message_retention_seconds = 1209600 # 14 days
  kms_master_key_id         = var.kms_key_arn

  tags = {
    Name  = "${var.name_prefix}-soc-agent-dlq"
    Agent = "soc-analyst"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "soc_agent" {
  name              = "/aws/lambda/agent-soc-analyst"
  retention_in_days = 30

  tags = {
    Name  = "${var.name_prefix}-soc-agent-logs"
    Agent = "soc-analyst"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "soc_agent_errors" {
  alarm_name          = "${var.name_prefix}-soc-agent-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "SOC Analyst Agent Lambda errors detected"

  dimensions = {
    FunctionName = aws_lambda_function.soc_analyst.function_name
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = {
    Name  = "${var.name_prefix}-soc-agent-errors-alarm"
    Agent = "soc-analyst"
  }
}

resource "aws_cloudwatch_metric_alarm" "soc_agent_latency" {
  alarm_name          = "${var.name_prefix}-soc-agent-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p95"
  threshold           = 25000
  alarm_description   = "SOC Analyst Agent p95 latency exceeds 25 seconds"

  dimensions = {
    FunctionName = aws_lambda_function.soc_analyst.function_name
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = {
    Name  = "${var.name_prefix}-soc-agent-latency-alarm"
    Agent = "soc-analyst"
  }
}
