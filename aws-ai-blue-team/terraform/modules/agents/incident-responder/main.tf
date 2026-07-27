# =============================================================================
# Incident Responder Agent Module
# =============================================================================
# Deploys the IR Agent Lambda, Slack approval handler, DynamoDB pending
# approvals table, and all associated monitoring.
# =============================================================================

data "archive_file" "incident_responder" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../lambdas/agent-incident-responder"
  output_path = "${path.module}/agent-incident-responder.zip"
}

data "archive_file" "slack_approval_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../lambdas/slack-approval-handler"
  output_path = "${path.module}/slack-approval-handler.zip"
}

# -----------------------------------------------------------------------------
# IR Agent Lambda
# -----------------------------------------------------------------------------
resource "aws_lambda_function" "incident_responder" {
  filename         = data.archive_file.incident_responder.output_path
  function_name    = "agent-incident-responder"
  role             = var.agent_role_arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.incident_responder.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 1024
  timeout          = 55
  reserved_concurrent_executions = 5

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      S3_BUCKET_NAME          = var.s3_bucket_name
      BASELINE_KEY            = "baselines/latest/baseline.json"
      OPENSEARCH_ENDPOINT     = var.opensearch_endpoint
      CEDAR_EVALUATOR_ARN     = var.cedar_evaluator_arn
      PENDING_APPROVALS_TABLE = aws_dynamodb_table.pending_approvals.name
      SLACK_WEBHOOK_URL       = var.slack_webhook_url
      GITHUB_REPO             = var.github_repo
      AI_MODEL_ID             = "anthropic.claude-3-haiku-20240307-v1:0"
      AI_ENABLED              = "true"
      ENVIRONMENT             = "dev"
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.ir_agent_dlq.arn
  }

  tags = {
    Name  = "${var.name_prefix}-agent-incident-responder"
    Agent = "incident-responder"
  }
}

# -----------------------------------------------------------------------------
# Slack Approval Handler Lambda
# -----------------------------------------------------------------------------
resource "aws_lambda_function" "slack_approval_handler" {
  filename         = data.archive_file.slack_approval_handler.output_path
  function_name    = "slack-approval-handler"
  role             = aws_iam_role.slack_handler_role.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.slack_approval_handler.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 256
  timeout          = 10

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      PENDING_APPROVALS_TABLE = aws_dynamodb_table.pending_approvals.name
      IR_AGENT_FUNCTION_NAME  = aws_lambda_function.incident_responder.function_name
      SLACK_WEBHOOK_URL       = var.slack_webhook_url
    }
  }

  tags = {
    Name  = "${var.name_prefix}-slack-approval-handler"
    Agent = "incident-responder"
  }
}

resource "aws_iam_role" "slack_handler_role" {
  name = "${var.name_prefix}-slack-handler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${var.name_prefix}-slack-handler-role" }
}

resource "aws_iam_role_policy" "slack_handler" {
  name = "slack-handler-permissions"
  role = aws_iam_role.slack_handler_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.pending_approvals.arn
      },
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.incident_responder.arn
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      }
    ]
  })
}

# API Gateway route for Slack approval callbacks
resource "aws_apigatewayv2_route" "slack_approval" {
  api_id    = var.api_gateway_id
  route_key = "POST /slack/approval"
  target    = "integrations/${aws_apigatewayv2_integration.slack_handler.id}"
}

resource "aws_apigatewayv2_integration" "slack_handler" {
  api_id                 = var.api_gateway_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.slack_approval_handler.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_lambda_permission" "allow_apigw_slack" {
  statement_id  = "AllowAPIGatewaySlackApproval"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slack_approval_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_gateway_execution_arn}/*/*"
}

# -----------------------------------------------------------------------------
# DynamoDB - Pending Approvals
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "pending_approvals" {
  name         = "${var.name_prefix}-pending-approvals"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "incident_id"

  attribute {
    name = "incident_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name  = "${var.name_prefix}-pending-approvals"
    Agent = "incident-responder"
  }
}

# -----------------------------------------------------------------------------
# Dead-Letter Queue
# -----------------------------------------------------------------------------
resource "aws_sqs_queue" "ir_agent_dlq" {
  name                      = "${var.name_prefix}-ir-agent-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = var.kms_key_arn

  tags = {
    Name  = "${var.name_prefix}-ir-agent-dlq"
    Agent = "incident-responder"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Monitoring
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ir_agent" {
  name              = "/aws/lambda/agent-incident-responder"
  retention_in_days = 30
  tags = { Name = "${var.name_prefix}-ir-agent-logs" }
}

resource "aws_cloudwatch_log_group" "slack_handler" {
  name              = "/aws/lambda/slack-approval-handler"
  retention_in_days = 30
  tags = { Name = "${var.name_prefix}-slack-handler-logs" }
}

resource "aws_cloudwatch_metric_alarm" "ir_errors" {
  alarm_name          = "${var.name_prefix}-ir-agent-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Incident Responder Agent errors - remediation may have failed"
  dimensions          = { FunctionName = aws_lambda_function.incident_responder.function_name }
  alarm_actions       = [var.sns_alert_topic_arn]
  tags                = { Name = "${var.name_prefix}-ir-errors-alarm" }
}

resource "aws_cloudwatch_metric_alarm" "ir_mttr" {
  alarm_name          = "${var.name_prefix}-ir-agent-mttr"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p95"
  threshold           = 55000
  alarm_description   = "IR Agent p95 duration approaching timeout - remediations may be slow"
  dimensions          = { FunctionName = aws_lambda_function.incident_responder.function_name }
  alarm_actions       = [var.sns_alert_topic_arn]
  tags                = { Name = "${var.name_prefix}-ir-mttr-alarm" }
}
