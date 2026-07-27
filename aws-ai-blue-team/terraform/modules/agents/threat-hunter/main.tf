# =============================================================================
# Threat Hunter Agent Module
# =============================================================================

data "archive_file" "threat_hunter" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../lambdas/agent-threat-hunter"
  output_path = "${path.module}/agent-threat-hunter.zip"
}

resource "aws_lambda_function" "threat_hunter" {
  filename         = data.archive_file.threat_hunter.output_path
  function_name    = "agent-threat-hunter"
  role             = var.agent_role_arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.threat_hunter.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 512
  timeout          = 900
  reserved_concurrent_executions = 1

  tracing_config { mode = "Active" }

  environment {
    variables = {
      S3_BUCKET_NAME      = var.s3_bucket_name
      OPENSEARCH_ENDPOINT = var.opensearch_endpoint
      SLACK_WEBHOOK_URL   = var.slack_webhook_url
      AI_MODEL_ID         = "anthropic.claude-3-haiku-20240307-v1:0"
      AI_ENABLED          = "true"
      ENVIRONMENT         = "dev"
    }
  }

  tags = { Name = "${var.name_prefix}-agent-threat-hunter", Agent = "threat-hunter" }
}

resource "aws_cloudwatch_event_rule" "hunter_6h" {
  name                = "${var.name_prefix}-threat-hunter-6h"
  description         = "Trigger Threat Hunter every 6 hours"
  schedule_expression = "cron(0 */6 * * ? *)"
  tags                = { Name = "${var.name_prefix}-hunter-schedule" }
}

resource "aws_cloudwatch_event_target" "hunter_lambda" {
  rule      = aws_cloudwatch_event_rule.hunter_6h.name
  target_id = "threat-hunter"
  arn       = aws_lambda_function.threat_hunter.arn
}

resource "aws_lambda_permission" "hunter_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.threat_hunter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.hunter_6h.arn
}

resource "aws_cloudwatch_log_group" "threat_hunter" {
  name              = "/aws/lambda/agent-threat-hunter"
  retention_in_days = 30
  tags              = { Name = "${var.name_prefix}-threat-hunter-logs" }
}
