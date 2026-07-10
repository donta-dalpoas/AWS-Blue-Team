# =============================================================================
# OpenSearch Module - Security Analytics Cluster
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Service-linked role (created once per account)
resource "aws_iam_service_linked_role" "opensearch" {
  aws_service_name = "opensearchservice.amazonaws.com"
  description      = "Service-linked role for OpenSearch"

  lifecycle {
    ignore_changes = [description]
  }
}

# -----------------------------------------------------------------------------
# OpenSearch Domain
# -----------------------------------------------------------------------------
resource "aws_opensearch_domain" "security" {
  domain_name    = "security-analytics"
  engine_version = "OpenSearch_2.11"

  cluster_config {
    instance_type          = var.instance_type
    instance_count         = var.instance_count
    zone_awareness_enabled = var.instance_count > 1

    dynamic "zone_awareness_config" {
      for_each = var.instance_count > 1 ? [1] : []
      content {
        availability_zone_count = min(var.instance_count, 3)
      }
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = var.ebs_volume_size
  }

  encrypt_at_rest {
    enabled    = true
    kms_key_id = var.kms_key_arn
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  advanced_security_options {
    enabled                        = true
    internal_user_database_enabled = true
    master_user_options {
      master_user_name     = var.master_user_name
      master_user_password = var.master_user_password
    }
  }

  # VPC config (if subnet IDs provided)
  dynamic "vpc_options" {
    for_each = length(var.vpc_subnet_ids) > 0 ? [1] : []
    content {
      subnet_ids         = var.vpc_subnet_ids
      security_group_ids = [var.vpc_security_group_id]
    }
  }

  # Logging
  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_slow_search.arn
    log_type                 = "SEARCH_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_index_slow.arn
    log_type                 = "INDEX_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_error.arn
    log_type                 = "ES_APPLICATION_LOGS"
  }

  auto_tune_options {
    desired_state = "DISABLED"
  }

  tags = {
    Name = "${var.name_prefix}-opensearch"
  }

  depends_on = [aws_iam_service_linked_role.opensearch]

  timeouts {
    create = "60m"
    update = "60m"
    delete = "30m"
  }
}

# Access policy (if not VPC mode)
resource "aws_opensearch_domain_policy" "security" {
  count       = length(var.vpc_subnet_ids) == 0 ? 1 : 0
  domain_name = aws_opensearch_domain.security.domain_name

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "es:*"
        Resource = "${aws_opensearch_domain.security.arn}/*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# CloudWatch Log Groups for OpenSearch
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "opensearch_slow_search" {
  name              = "/aws/opensearch/security-analytics/slow-search"
  retention_in_days = 14

  tags = {
    Name = "${var.name_prefix}-opensearch-slow-search"
  }
}

resource "aws_cloudwatch_log_group" "opensearch_index_slow" {
  name              = "/aws/opensearch/security-analytics/slow-index"
  retention_in_days = 14

  tags = {
    Name = "${var.name_prefix}-opensearch-index-slow"
  }
}

resource "aws_cloudwatch_log_group" "opensearch_error" {
  name              = "/aws/opensearch/security-analytics/error"
  retention_in_days = 30

  tags = {
    Name = "${var.name_prefix}-opensearch-error"
  }
}

# CloudWatch Log Resource Policy (required for OpenSearch to write logs)
resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "${var.name_prefix}-opensearch-log-policy"

  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "es.amazonaws.com"
        }
        Action = [
          "logs:PutLogEvents",
          "logs:CreateLogStream"
        ]
        Resource = [
          "${aws_cloudwatch_log_group.opensearch_slow_search.arn}:*",
          "${aws_cloudwatch_log_group.opensearch_index_slow.arn}:*",
          "${aws_cloudwatch_log_group.opensearch_error.arn}:*"
        ]
      }
    ]
  })
}
