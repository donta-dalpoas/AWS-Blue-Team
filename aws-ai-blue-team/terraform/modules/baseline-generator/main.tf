# =============================================================================
# Baseline Generator Module - Weekly Posture Snapshot Lambda
# =============================================================================

data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# Lambda Function
# -----------------------------------------------------------------------------
data "archive_file" "baseline_generator" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/baseline-generator"
  output_path = "${path.module}/baseline-generator.zip"
}

resource "aws_lambda_function" "baseline_generator" {
  filename         = data.archive_file.baseline_generator.output_path
  function_name    = "baseline-generator"
  role             = aws_iam_role.baseline_generator.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.baseline_generator.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 512
  timeout          = 300
  reserved_concurrent_executions = 1

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      BUCKET_NAME     = var.s3_bucket_name
      BASELINE_PREFIX = "baselines/"
      ACCOUNT_ID      = var.account_id
      REGIONS         = join(",", var.active_regions)
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.baseline_dlq.arn
  }

  tags = {
    Name = "${var.name_prefix}-baseline-generator"
  }
}

# -----------------------------------------------------------------------------
# IAM Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "baseline_generator" {
  name = "baseline-generator-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.name_prefix}-baseline-generator-role"
  }
}

resource "aws_iam_role_policy" "baseline_generator" {
  name = "baseline-generator-permissions"
  role = aws_iam_role.baseline_generator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # IAM read operations
      {
        Effect = "Allow"
        Action = [
          "iam:ListUsers",
          "iam:ListUserPolicies",
          "iam:ListAttachedUserPolicies",
          "iam:ListMFADevices",
          "iam:ListAccessKeys",
          "iam:GetAccessKeyLastUsed",
          "iam:ListGroupsForUser",
          "iam:ListRoles",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:GetRole"
        ]
        Resource = "*"
      },
      # EC2 security group read
      {
        Effect   = "Allow"
        Action   = ["ec2:DescribeSecurityGroups", "ec2:DescribeRegions"]
        Resource = "*"
      },
      # S3 read (bucket configs)
      {
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketAcl",
          "s3:GetBucketPolicy",
          "s3:GetBucketVersioning",
          "s3:GetEncryptionConfiguration",
          "s3:GetBucketPublicAccessBlock",
          "s3:GetBucketLogging",
          "s3:GetLifecycleConfiguration",
          "s3:GetBucketTagging",
          "s3:GetBucketLocation"
        ]
        Resource = "*"
      },
      # GuardDuty read
      {
        Effect   = "Allow"
        Action   = ["guardduty:ListDetectors", "guardduty:GetDetector"]
        Resource = "*"
      },
      # S3 write (baseline output)
      {
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${var.s3_bucket_arn}/baselines/*"
      },
      # KMS
      {
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
        Resource = var.kms_key_arn
      },
      # X-Ray
      {
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
      # CloudWatch Logs
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:${var.account_id}:*"
      },
      # SQS DLQ
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.baseline_dlq.arn
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# EventBridge Schedule (Weekly - Sunday 00:00 UTC)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "baseline_weekly" {
  name                = "baseline-generator-weekly"
  description         = "Trigger baseline generator Lambda every Sunday at 00:00 UTC"
  schedule_expression = "cron(0 0 ? * SUN *)"

  tags = {
    Name = "${var.name_prefix}-baseline-schedule"
  }
}

resource "aws_cloudwatch_event_target" "baseline_lambda" {
  rule      = aws_cloudwatch_event_rule.baseline_weekly.name
  target_id = "baseline-generator"
  arn       = aws_lambda_function.baseline_generator.arn

  retry_policy {
    maximum_retry_attempts       = 2
    maximum_event_age_in_seconds = 3600
  }

  dead_letter_config {
    arn = aws_sqs_queue.baseline_dlq.arn
  }
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.baseline_generator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.baseline_weekly.arn
}

# -----------------------------------------------------------------------------
# Dead-Letter Queue
# -----------------------------------------------------------------------------
resource "aws_sqs_queue" "baseline_dlq" {
  name                      = "${var.name_prefix}-baseline-dlq"
  message_retention_seconds = 1209600 # 14 days
  kms_master_key_id         = var.kms_key_arn

  tags = {
    Name = "${var.name_prefix}-baseline-dlq"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Alarm - Lambda Errors
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "baseline_errors" {
  alarm_name          = "${var.name_prefix}-baseline-generator-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Baseline Generator Lambda failed - manual investigation required"

  dimensions = {
    FunctionName = aws_lambda_function.baseline_generator.function_name
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = {
    Name = "${var.name_prefix}-baseline-errors-alarm"
  }
}
