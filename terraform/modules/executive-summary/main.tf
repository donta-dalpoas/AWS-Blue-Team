# =============================================================================
# Executive Summary Agent - Terraform Module
# =============================================================================
# Epic 5 Subissue 2: Deploys the weekly executive brief Lambda with
# EventBridge schedule (Monday 8AM UTC), IAM role, and CloudWatch logging.
# =============================================================================

# -----------------------------------------------------------------------------
# IAM Role for the Lambda
# -----------------------------------------------------------------------------
resource "aws_iam_role" "executive_summary" {
  name = "${var.name_prefix}-executive-summary-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = var.name_prefix
    Epic    = "5"
    Agent   = "executive-summary"
  }
}

# CloudWatch Logs policy
resource "aws_iam_role_policy" "executive_summary_logs" {
  name = "${var.name_prefix}-executive-summary-logs"
  role = aws_iam_role.executive_summary.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${var.account_id}:log-group:/aws/lambda/${var.name_prefix}-executive-summary:*"
      }
    ]
  })
}

# OpenSearch access policy (read-only)
resource "aws_iam_role_policy" "executive_summary_opensearch" {
  name = "${var.name_prefix}-executive-summary-opensearch"
  role = aws_iam_role.executive_summary.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "es:ESHttpGet",
          "es:ESHttpPost"
        ]
        Resource = "${var.opensearch_domain_arn}/*"
      }
    ]
  })
}

# Secrets Manager access (for GitHub token)
resource "aws_iam_role_policy" "executive_summary_secrets" {
  name = "${var.name_prefix}-executive-summary-secrets"
  role = aws_iam_role.executive_summary.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${var.name_prefix}/github-token-*"
        ]
      }
    ]
  })
}

# X-Ray tracing
resource "aws_iam_role_policy" "executive_summary_xray" {
  name = "${var.name_prefix}-executive-summary-xray"
  role = aws_iam_role.executive_summary.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Lambda Function
# -----------------------------------------------------------------------------
data "archive_file" "executive_summary" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/executive-summary"
  output_path = "${path.module}/files/executive-summary.zip"
}

resource "aws_lambda_function" "executive_summary" {
  function_name    = "${var.name_prefix}-executive-summary"
  description      = "Weekly executive security brief generator (Epic 5)"
  role             = aws_iam_role.executive_summary.arn
  handler          = "handler.handler"
  runtime          = "python3.11"
  architectures    = ["arm64"]
  timeout          = 600 # 10 minutes
  memory_size      = 512
  filename         = data.archive_file.executive_summary.output_path
  source_code_hash = data.archive_file.executive_summary.output_base64sha256

  environment {
    variables = {
      OPENSEARCH_ENDPOINT = var.opensearch_endpoint
      GITHUB_TOKEN        = var.github_token
      GITHUB_REPO         = var.github_repo
      LOG_LEVEL           = var.log_level
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Project = var.name_prefix
    Epic    = "5"
    Agent   = "executive-summary"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "executive_summary" {
  name              = "/aws/lambda/${var.name_prefix}-executive-summary"
  retention_in_days = 30

  tags = {
    Project = var.name_prefix
    Epic    = "5"
    Agent   = "executive-summary"
  }
}

# -----------------------------------------------------------------------------
# EventBridge Schedule (Monday 8AM UTC)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "executive_summary_schedule" {
  name                = "${var.name_prefix}-executive-summary-schedule"
  description         = "Triggers Executive Summary Agent every Monday at 8AM UTC"
  schedule_expression = "cron(0 8 ? * MON *)"

  tags = {
    Project = var.name_prefix
    Epic    = "5"
    Agent   = "executive-summary"
  }
}

resource "aws_cloudwatch_event_target" "executive_summary_target" {
  rule      = aws_cloudwatch_event_rule.executive_summary_schedule.name
  target_id = "executive-summary-lambda"
  arn       = aws_lambda_function.executive_summary.arn

  input = jsonencode({
    source      = "scheduled"
    detail-type = "weekly-executive-summary"
  })
}

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.executive_summary.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.executive_summary_schedule.arn
}

# -----------------------------------------------------------------------------
# CloudWatch Alarm (failure detection)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "executive_summary_errors" {
  alarm_name          = "${var.name_prefix}-executive-summary-errors"
  alarm_description   = "Executive Summary Agent Lambda errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 3600
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.executive_summary.function_name
  }

  alarm_actions = var.sns_alert_topic_arn != "" ? [var.sns_alert_topic_arn] : []

  tags = {
    Project = var.name_prefix
    Epic    = "5"
    Agent   = "executive-summary"
  }
}
