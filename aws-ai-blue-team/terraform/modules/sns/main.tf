# =============================================================================
# SNS Module - Security Findings Topic + EventBridge Rules
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# SNS Topics
# -----------------------------------------------------------------------------
resource "aws_sns_topic" "security_findings" {
  name              = "${var.name_prefix}-security-findings"
  kms_master_key_id = var.kms_key_arn

  tags = {
    Name = "${var.name_prefix}-security-findings"
  }
}

resource "aws_sns_topic" "agent_alerts" {
  name              = "${var.name_prefix}-agent-alerts"
  kms_master_key_id = var.kms_key_arn

  tags = {
    Name = "${var.name_prefix}-agent-alerts"
  }
}

# Topic policy: allow EventBridge to publish
resource "aws_sns_topic_policy" "security_findings" {
  arn = aws_sns_topic.security_findings.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgePublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sns:Publish"
        Resource = aws_sns_topic.security_findings.arn
      },
      {
        Sid    = "AllowAccountPublish"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "sns:Publish"
        Resource = aws_sns_topic.security_findings.arn
      }
    ]
  })
}

resource "aws_sns_topic_policy" "agent_alerts" {
  arn = aws_sns_topic.agent_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudWatchAlarms"
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action   = "sns:Publish"
        Resource = aws_sns_topic.agent_alerts.arn
      },
      {
        Sid    = "AllowAccountPublish"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "sns:Publish"
        Resource = aws_sns_topic.agent_alerts.arn
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# EventBridge Rules
# -----------------------------------------------------------------------------

# Rule 1: Forward all GuardDuty findings to SNS
resource "aws_cloudwatch_event_rule" "guardduty_findings" {
  name        = "${var.name_prefix}-guardduty-to-sns"
  description = "Forward all GuardDuty findings to security-findings SNS topic"

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
  })

  tags = {
    Name = "${var.name_prefix}-guardduty-to-sns"
  }
}

resource "aws_cloudwatch_event_target" "guardduty_to_sns" {
  rule      = aws_cloudwatch_event_rule.guardduty_findings.name
  target_id = "guardduty-to-sns"
  arn       = aws_sns_topic.security_findings.arn
}

# Rule 2: Forward high-severity SecurityHub findings to SNS
resource "aws_cloudwatch_event_rule" "securityhub_findings" {
  name        = "${var.name_prefix}-securityhub-to-sns"
  description = "Forward CRITICAL/HIGH/MEDIUM SecurityHub findings to SNS"

  event_pattern = jsonencode({
    source      = ["aws.securityhub"]
    detail-type = ["Security Hub Findings - Imported"]
    detail = {
      findings = {
        Severity = {
          Label = ["CRITICAL", "HIGH", "MEDIUM"]
        }
      }
    }
  })

  tags = {
    Name = "${var.name_prefix}-securityhub-to-sns"
  }
}

resource "aws_cloudwatch_event_target" "securityhub_to_sns" {
  rule      = aws_cloudwatch_event_rule.securityhub_findings.name
  target_id = "securityhub-to-sns"
  arn       = aws_sns_topic.security_findings.arn
}

# -----------------------------------------------------------------------------
# Dead-Letter Queue for failed SNS deliveries
# -----------------------------------------------------------------------------
resource "aws_sqs_queue" "sns_dlq" {
  name                      = "${var.name_prefix}-sns-dlq"
  message_retention_seconds = 1209600 # 14 days
  kms_master_key_id         = var.kms_key_arn

  tags = {
    Name = "${var.name_prefix}-sns-dlq"
  }
}
