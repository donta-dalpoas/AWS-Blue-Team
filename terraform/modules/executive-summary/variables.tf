# =============================================================================
# Executive Summary Agent - Module Variables
# =============================================================================

variable "name_prefix" {
  description = "Naming prefix for all resources"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "opensearch_endpoint" {
  description = "OpenSearch domain endpoint (without https://)"
  type        = string
}

variable "opensearch_domain_arn" {
  description = "OpenSearch domain ARN for IAM policy"
  type        = string
}

variable "github_token" {
  description = "GitHub API token for committing weekly reports"
  type        = string
  sensitive   = true
}

variable "github_repo" {
  description = "GitHub repository (owner/repo format)"
  type        = string
  default     = "donta-dalpoas/AWS-Blue-Team"
}

variable "sns_alert_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarm notifications"
  type        = string
  default     = ""
}

variable "log_level" {
  description = "Lambda log level"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "Log level must be DEBUG, INFO, WARNING, or ERROR."
  }
}
