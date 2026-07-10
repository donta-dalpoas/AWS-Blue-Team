# =============================================================================
# Ingestion Module - SQS + Lambda Pipeline for OpenSearch
# =============================================================================
# Creates SQS queue, S3 event notifications, Lambda ingestion function,
# and wires them together for real-time log indexing.
# =============================================================================

# -----------------------------------------------------------------------------
# SQS Queue - Log Ingestion
# -----------------------------------------------------------------------------
resource "aws_sqs_queue" "ingestion" {
  name                       = "${var.name_prefix}-log-ingestion"
  visibility_timeout_seconds = 360 # 6x Lambda timeout
  message_retention_seconds  = 1209600 # 14 days
  receive_wait_time_seconds  = 20
  kms_master_key_id          = var.kms_key_arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "${var.name_prefix}-log-ingestion"
  }
}

resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "${var.name_prefix}-log-ingestion-dlq"
  message_retention_seconds = 1209600 # 14 days
  kms_master_key_id         = var.kms_key_arn

  tags = {
    Name = "${var.name_prefix}-log-ingestion-dlq"
  }
}

# SQS policy: allow S3 to send messages
resource "aws_sqs_queue_policy" "allow_s3" {
  queue_url = aws_sqs_queue.ingestion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowS3SendMessage"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.ingestion.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = var.s3_bucket_arn
          }
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# S3 Event Notifications -> SQS
# -----------------------------------------------------------------------------
resource "aws_s3_bucket_notification" "log_notifications" {
  bucket = var.s3_bucket_name

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "cloudtrail/"
  }

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "vpc-flow-logs/"
  }

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "guardduty/"
  }

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "securityhub/"
  }

  depends_on = [aws_sqs_queue_policy.allow_s3]
}

# -----------------------------------------------------------------------------
# Lambda - Log Ingestor
# -----------------------------------------------------------------------------
data "archive_file" "log_ingestor" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/log-ingestor"
  output_path = "${path.module}/log-ingestor.zip"
}

resource "aws_lambda_function" "log_ingestor" {
  filename         = data.archive_file.log_ingestor.output_path
  function_name    = "log-ingestor"
  role             = aws_iam_role.log_ingestor.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.log_ingestor.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 512
  timeout          = 60
  reserved_concurrent_executions = var.lambda_concurrency

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      OPENSEARCH_ENDPOINT     = var.opensearch_endpoint
      OPENSEARCH_INDEX_PREFIX = "security-logs"
      OPENSEARCH_REGION       = data.aws_region.current.name
      OPENSEARCH_AUTH_TYPE    = "iam"
      BATCH_SIZE             = tostring(var.batch_size)
      MAX_RETRIES            = "3"
    }
  }

  tags = {
    Name = "${var.name_prefix}-log-ingestor"
  }
}

data "aws_region" "current" {}

# Event source mapping: SQS -> Lambda
resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn                   = aws_sqs_queue.ingestion.arn
  function_name                      = aws_lambda_function.log_ingestor.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 30
  enabled                            = true

  function_response_types = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = var.lambda_concurrency
  }
}

# -----------------------------------------------------------------------------
# IAM Role - Log Ingestor
# -----------------------------------------------------------------------------
resource "aws_iam_role" "log_ingestor" {
  name = "log-ingestor-execution-role"

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
    Name = "${var.name_prefix}-log-ingestor-role"
  }
}

resource "aws_iam_role_policy" "log_ingestor" {
  name = "log-ingestor-permissions"
  role = aws_iam_role.log_ingestor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 read
      {
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = [
          "${var.s3_bucket_arn}/cloudtrail/*",
          "${var.s3_bucket_arn}/vpc-flow-logs/*",
          "${var.s3_bucket_arn}/guardduty/*",
          "${var.s3_bucket_arn}/securityhub/*"
        ]
      },
      # OpenSearch write
      {
        Effect = "Allow"
        Action = [
          "es:ESHttpPost",
          "es:ESHttpPut"
        ]
        Resource = "${var.opensearch_domain_arn}/*"
      },
      # SQS
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.ingestion.arn
      },
      # KMS
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
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
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Alarms
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "${var.name_prefix}-ingestion-dlq-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Ingestion DLQ has messages - investigate failed log processing"

  dimensions = {
    QueueName = aws_sqs_queue.ingestion_dlq.name
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = {
    Name = "${var.name_prefix}-ingestion-dlq-alarm"
  }
}
