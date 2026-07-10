# =============================================================================
# GuardDuty Module
# =============================================================================
# Enables GuardDuty detector with all available protection plans and
# configures finding export to S3.
# =============================================================================

resource "aws_guardduty_detector" "main" {
  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = true
        }
      }
    }
  }

  tags = {
    Name = "${var.name_prefix}-guardduty"
  }
}

# Export findings to S3 (requires bucket prefix to exist)
# NOTE: Uncomment after the S3 bucket has been created and initial objects exist
# resource "aws_guardduty_publishing_destination" "s3" {
#   detector_id     = aws_guardduty_detector.main.id
#   destination_arn = "${var.s3_bucket_arn}/guardduty/"
#   kms_key_arn     = var.kms_key_arn
#   destination_type = "S3"
# }
