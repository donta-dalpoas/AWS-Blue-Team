# =============================================================================
# CloudTrail Module - Multi-Region Trail
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# CloudWatch Log Group for CloudTrail
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "cloudtrail" {
  name              = "/aws/cloudtrail/${var.name_prefix}"
  retention_in_days = 30

  tags = {
    Name = "${var.name_prefix}-cloudtrail-logs"
  }
}

# -----------------------------------------------------------------------------
# IAM Role for CloudTrail -> CloudWatch Logs delivery
# -----------------------------------------------------------------------------
resource "aws_iam_role" "cloudtrail_cloudwatch" {
  name = "${var.name_prefix}-cloudtrail-cw-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.name_prefix}-cloudtrail-cw-role"
  }
}

resource "aws_iam_role_policy" "cloudtrail_cloudwatch" {
  name = "cloudwatch-logs-delivery"
  role = aws_iam_role.cloudtrail_cloudwatch.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# CloudTrail
# -----------------------------------------------------------------------------
resource "aws_cloudtrail" "main" {
  name                          = "${var.name_prefix}-trail"
  s3_bucket_name                = var.s3_bucket_name
  s3_key_prefix                 = "cloudtrail"
  is_multi_region_trail         = true
  is_organization_trail         = false
  include_global_service_events = true
  enable_log_file_validation    = true
  kms_key_id                    = var.kms_key_arn
  cloud_watch_logs_group_arn    = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
  cloud_watch_logs_role_arn     = aws_iam_role.cloudtrail_cloudwatch.arn
  enable_logging                = true

  # Management events
  event_selector {
    read_write_type           = "All"
    include_management_events = true

    # S3 data events (all buckets)
    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3"]
    }
  }

  # Lambda invocation data events
  event_selector {
    read_write_type           = "All"
    include_management_events = false

    data_resource {
      type   = "AWS::Lambda::Function"
      values = ["arn:aws:lambda"]
    }
  }

  # Insight events
  insight_selector {
    insight_type = "ApiCallRateInsight"
  }

  insight_selector {
    insight_type = "ApiErrorRateInsight"
  }

  tags = {
    Name = "${var.name_prefix}-trail"
  }

  depends_on = [aws_iam_role_policy.cloudtrail_cloudwatch]
}
