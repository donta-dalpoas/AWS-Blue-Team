# =============================================================================
# AgentCore Identity Module - 5 Agent IAM Roles
# =============================================================================
# Creates least-privilege IAM roles for each AI security agent with
# permission boundaries preventing privilege escalation.
# =============================================================================

data "aws_caller_identity" "current" {}

locals {
  agents = ["soc-analyst", "incident-responder", "threat-hunter", "compliance-auditor", "red-team"]
}

# -----------------------------------------------------------------------------
# Permission Boundary (shared across all agent roles)
# -----------------------------------------------------------------------------
resource "aws_iam_policy" "agent_boundary" {
  name = "${var.name_prefix}-agent-permission-boundary"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "DenyIAMEscalation"
        Effect   = "Deny"
        Action   = [
          "iam:CreateRole",
          "iam:CreateUser",
          "iam:AttachRolePolicy",
          "iam:PutRolePolicy",
          "iam:AttachUserPolicy",
          "iam:PutUserPolicy"
        ]
        Resource = "*"
      },
      {
        Sid      = "DenyOrganizations"
        Effect   = "Deny"
        Action   = "organizations:*"
        Resource = "*"
      },
      {
        Sid      = "DenyAccountActions"
        Effect   = "Deny"
        Action   = "account:*"
        Resource = "*"
      },
      {
        Sid      = "DenyStateBucketAccess"
        Effect   = "Deny"
        Action   = "s3:*"
        Resource = [
          "arn:aws:s3:::${var.account_id}-*-terraform-state",
          "arn:aws:s3:::${var.account_id}-*-terraform-state/*"
        ]
      },
      {
        Sid      = "DenyModifyInfrastructure"
        Effect   = "Deny"
        Action   = [
          "lambda:DeleteFunction",
          "lambda:UpdateFunctionCode",
          "events:DeleteRule",
          "events:DisableRule",
          "cloudwatch:DeleteAlarms"
        ]
        Resource = "*"
      },
      {
        Sid      = "AllowEverythingElse"
        Effect   = "Allow"
        Action   = "*"
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${var.name_prefix}-agent-boundary"
  }
}

# -----------------------------------------------------------------------------
# SOC Analyst Agent Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "soc_analyst" {
  name                 = "agent-soc-analyst"
  permissions_boundary = aws_iam_policy.agent_boundary.arn

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

  tags = { Name = "agent-soc-analyst" }
}

resource "aws_iam_role_policy" "soc_analyst" {
  name = "soc-analyst-permissions"
  role = aws_iam_role.soc_analyst.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = [
          "${var.s3_bucket_arn}/cloudtrail/*",
          "${var.s3_bucket_arn}/vpc-flow-logs/*",
          "${var.s3_bucket_arn}/guardduty/*",
          "${var.s3_bucket_arn}/securityhub/*",
          "${var.s3_bucket_arn}/baselines/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["es:ESHttpGet", "es:ESHttpPost"]
        Resource = "${var.opensearch_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "sns:Publish"
        Resource = var.sns_topic_arn
      },
      {
        Effect   = "Allow"
        Action   = "cloudtrail:LookupEvents"
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.kms_key_arn
      },
      {
        Effect = "Allow"
        Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:${var.account_id}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = "arn:aws:sqs:*:${var.account_id}:*-soc-agent-dlq"
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = "arn:aws:lambda:*:${var.account_id}:function:agent-*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Incident Responder Agent Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "incident_responder" {
  name                 = "agent-incident-responder"
  permissions_boundary = aws_iam_policy.agent_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "agent-incident-responder" }
}

resource "aws_iam_role_policy" "incident_responder" {
  name = "incident-responder-permissions"
  role = aws_iam_role.incident_responder.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Containment"
        Effect = "Allow"
        Action = [
          "iam:DetachUserPolicy",
          "iam:DetachRolePolicy",
          "iam:UpdateAccessKey",
          "iam:ListAttachedUserPolicies",
          "iam:ListAttachedRolePolicies"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3Containment"
        Effect = "Allow"
        Action = [
          "s3:PutBucketPolicy",
          "s3:GetBucketPolicy",
          "s3:PutPublicAccessBlock"
        ]
        Resource = "*"
      },
      {
        Sid    = "EC2Containment"
        Effect = "Allow"
        Action = ["ec2:RevokeSecurityGroupIngress", "ec2:DescribeSecurityGroups"]
        Resource = "*"
      },
      {
        Sid    = "CloudTrailRestore"
        Effect = "Allow"
        Action = "cloudtrail:StartLogging"
        Resource = "*"
      },
      {
        Sid    = "ForensicWrite"
        Effect = "Allow"
        Action = "s3:PutObject"
        Resource = "${var.s3_bucket_arn}/forensics/*"
      },
      {
        Sid    = "BaselineRead"
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = "${var.s3_bucket_arn}/baselines/*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.kms_key_arn
      },
      {
        Effect = "Allow"
        Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:${var.account_id}:*"
      },
      {
        Sid    = "DLQAndLambda"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = "arn:aws:sqs:*:${var.account_id}:*-ir-agent-dlq"
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = "arn:aws:lambda:*:${var.account_id}:function:cedar-policy-evaluator"
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = "arn:aws:dynamodb:*:${var.account_id}:table/*-pending-approvals"
      },
      {
        Effect = "Allow"
        Action = ["cloudtrail:GetTrailStatus", "iam:ListAccessKeys", "s3:GetPublicAccessBlock"]
        Resource = "*"
      },
      # Explicit denies
      {
        Sid    = "DenyCreation"
        Effect = "Deny"
        Action = [
          "iam:CreateUser",
          "iam:CreateRole",
          "iam:AttachUserPolicy",
          "iam:AttachRolePolicy",
          "iam:PutUserPolicy",
          "iam:PutRolePolicy"
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyDeletion"
        Effect = "Deny"
        Action = [
          "s3:DeleteBucket",
          "s3:DeleteObject",
          "ec2:TerminateInstances",
          "ec2:DeleteSecurityGroup"
        ]
        Resource = "*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Threat Hunter Agent Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "threat_hunter" {
  name                 = "agent-threat-hunter"
  permissions_boundary = aws_iam_policy.agent_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "agent-threat-hunter" }
}

resource "aws_iam_role_policy" "threat_hunter" {
  name = "threat-hunter-permissions"
  role = aws_iam_role.threat_hunter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["es:ESHttpGet", "es:ESHttpPost"]
        Resource = "${var.opensearch_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${var.s3_bucket_arn}/baselines/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${var.s3_bucket_arn}/detections/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.kms_key_arn
      },
      {
        Effect = "Allow"
        Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:${var.account_id}:*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Compliance Auditor Agent Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "compliance_auditor" {
  name                 = "agent-compliance-auditor"
  permissions_boundary = aws_iam_policy.agent_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "agent-compliance-auditor" }
}

resource "aws_iam_role_policy" "compliance_auditor" {
  name = "compliance-auditor-permissions"
  role = aws_iam_role.compliance_auditor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AuditRead"
        Effect = "Allow"
        Action = [
          "iam:ListUsers", "iam:ListAccessKeys", "iam:GetAccessKeyLastUsed",
          "iam:ListMFADevices", "iam:ListAttachedUserPolicies",
          "ec2:DescribeSecurityGroups",
          "s3:ListAllMyBuckets", "s3:GetBucketAcl", "s3:GetBucketPolicy",
          "s3:GetBucketVersioning", "s3:GetEncryptionConfiguration",
          "s3:GetBucketPublicAccessBlock"
        ]
        Resource = "*"
      },
      {
        Sid    = "AutoRemediate"
        Effect = "Allow"
        Action = [
          "iam:DetachUserPolicy", "iam:UpdateAccessKey",
          "ec2:RevokeSecurityGroupIngress",
          "s3:PutPublicAccessBlock"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "es:ESHttpPost"
        Resource = "${var.opensearch_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.kms_key_arn
      },
      {
        Effect = "Allow"
        Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:${var.account_id}:*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Red Team Agent Role (SCOPED TO TEST RESOURCES ONLY)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "red_team" {
  name                 = "agent-red-team"
  permissions_boundary = aws_iam_policy.agent_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "agent-red-team" }
}

resource "aws_iam_role_policy" "red_team" {
  name = "red-team-permissions"
  role = aws_iam_role.red_team.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TestTrailOnly"
        Effect = "Allow"
        Action = "cloudtrail:StopLogging"
        Resource = "arn:aws:cloudtrail:*:${var.account_id}:trail/test-*"
      },
      {
        Sid    = "TestBucketOnly"
        Effect = "Allow"
        Action = ["s3:PutBucketPolicy", "s3:PutBucketAcl"]
        Resource = "arn:aws:s3:::*-test-*"
      },
      {
        Sid    = "TestUserOnly"
        Effect = "Allow"
        Action = ["iam:AttachUserPolicy", "iam:CreateUser", "iam:CreateAccessKey"]
        Resource = "arn:aws:iam::${var.account_id}:user/test-*"
      },
      {
        Sid    = "OpenSearchRead"
        Effect = "Allow"
        Action = ["es:ESHttpGet", "es:ESHttpPost"]
        Resource = "${var.opensearch_arn}/*"
      },
      {
        Sid    = "DetectionWrite"
        Effect = "Allow"
        Action = "s3:PutObject"
        Resource = "${var.s3_bucket_arn}/detections/*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        Resource = var.kms_key_arn
      },
      {
        Effect = "Allow"
        Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:${var.account_id}:*"
      }
    ]
  })
}
