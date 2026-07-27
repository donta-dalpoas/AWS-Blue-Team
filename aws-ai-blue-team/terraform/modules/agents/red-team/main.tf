# =============================================================================
# Red Team Agent Module
# =============================================================================

data "archive_file" "red_team" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../lambdas/agent-red-team"
  output_path = "${path.module}/agent-red-team.zip"
}

resource "aws_lambda_function" "red_team" {
  filename         = data.archive_file.red_team.output_path
  function_name    = "agent-red-team"
  role             = var.agent_role_arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.red_team.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 512
  timeout          = 900
  reserved_concurrent_executions = 1

  tracing_config { mode = "Active" }

  environment {
    variables = {
      S3_BUCKET_NAME           = var.s3_bucket_name
      OPENSEARCH_ENDPOINT      = var.opensearch_endpoint
      SLACK_WEBHOOK_URL        = var.slack_webhook_url
      DETECTION_WAIT_SECONDS   = "60"
      AI_MODEL_ID              = "anthropic.claude-3-haiku-20240307-v1:0"
      AI_ENABLED               = "true"
      ENVIRONMENT              = "dev"
    }
  }

  tags = { Name = "${var.name_prefix}-agent-red-team", Agent = "red-team" }
}

resource "aws_cloudwatch_event_rule" "redteam_weekly" {
  name                = "${var.name_prefix}-red-team-weekly"
  description         = "Trigger Red Team Agent every Sunday at 02:00 UTC"
  schedule_expression = "cron(0 2 ? * SUN *)"
  tags                = { Name = "${var.name_prefix}-redteam-schedule" }
}

resource "aws_cloudwatch_event_target" "redteam_lambda" {
  rule      = aws_cloudwatch_event_rule.redteam_weekly.name
  target_id = "red-team"
  arn       = aws_lambda_function.red_team.arn
}

resource "aws_lambda_permission" "redteam_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.red_team.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.redteam_weekly.arn
}

resource "aws_cloudwatch_log_group" "red_team" {
  name              = "/aws/lambda/agent-red-team"
  retention_in_days = 30
  tags              = { Name = "${var.name_prefix}-red-team-logs" }
}
