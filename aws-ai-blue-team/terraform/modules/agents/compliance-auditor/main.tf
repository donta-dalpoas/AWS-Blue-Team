# =============================================================================
# Compliance Auditor Agent Module
# =============================================================================

data "archive_file" "compliance_auditor" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../lambdas/agent-compliance-auditor"
  output_path = "${path.module}/agent-compliance-auditor.zip"
}

resource "aws_lambda_function" "compliance_auditor" {
  filename         = data.archive_file.compliance_auditor.output_path
  function_name    = "agent-compliance-auditor"
  role             = var.agent_role_arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.compliance_auditor.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 512
  timeout          = 300
  reserved_concurrent_executions = 1

  tracing_config { mode = "Active" }

  environment {
    variables = {
      S3_BUCKET_NAME      = var.s3_bucket_name
      OPENSEARCH_ENDPOINT = var.opensearch_endpoint
      SLACK_WEBHOOK_URL   = var.slack_webhook_url
      ENVIRONMENT         = "dev"
    }
  }

  tags = { Name = "${var.name_prefix}-agent-compliance-auditor", Agent = "compliance-auditor" }
}

resource "aws_cloudwatch_event_rule" "compliance_hourly" {
  name                = "${var.name_prefix}-compliance-auditor-hourly"
  description         = "Trigger Compliance Auditor every hour"
  schedule_expression = "cron(0 * * * ? *)"
  tags                = { Name = "${var.name_prefix}-compliance-schedule" }
}

resource "aws_cloudwatch_event_target" "compliance_lambda" {
  rule      = aws_cloudwatch_event_rule.compliance_hourly.name
  target_id = "compliance-auditor"
  arn       = aws_lambda_function.compliance_auditor.arn
}

resource "aws_lambda_permission" "compliance_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.compliance_auditor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.compliance_hourly.arn
}

resource "aws_cloudwatch_log_group" "compliance_auditor" {
  name              = "/aws/lambda/agent-compliance-auditor"
  retention_in_days = 30
  tags              = { Name = "${var.name_prefix}-compliance-auditor-logs" }
}
