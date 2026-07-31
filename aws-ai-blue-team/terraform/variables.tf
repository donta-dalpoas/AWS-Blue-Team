# =============================================================================
# Root Module Variables
# =============================================================================

# -----------------------------------------------------------------------------
# General
# -----------------------------------------------------------------------------
variable "account_id" {
  description = "AWS Account ID"
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Account ID must be a 12-digit number."
  }
}

variable "aws_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-east-1"
}

variable "active_regions" {
  description = "List of AWS regions to enable security services in"
  type        = list(string)
  default     = ["us-east-1", "us-west-2"]
}

variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}

variable "project_name" {
  description = "Project name for tagging and resource naming"
  type        = string
  default     = "aws-ai-blue-team"
}

# -----------------------------------------------------------------------------
# GitHub
# -----------------------------------------------------------------------------
variable "github_org" {
  description = "GitHub organization name"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "aws-ai-blue-team"
}

variable "github_token" {
  description = "GitHub API token for executive summary agent (optional)"
  type        = string
  sensitive   = true
  default     = "PLACEHOLDER_TOKEN_UPDATE_AFTER_DEPLOYMENT"
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------
variable "create_vpc" {
  description = "Whether to create a dedicated VPC for the platform"
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# -----------------------------------------------------------------------------
# OpenSearch
# -----------------------------------------------------------------------------
variable "opensearch_instance_type" {
  description = "OpenSearch instance type"
  type        = string
  default     = "t3.medium.search"
}

variable "opensearch_instance_count" {
  description = "Number of OpenSearch data nodes"
  type        = number
  default     = 2
}

variable "opensearch_ebs_volume_size" {
  description = "EBS volume size in GB per OpenSearch node"
  type        = number
  default     = 100
}

# -----------------------------------------------------------------------------
# S3 Lifecycle
# -----------------------------------------------------------------------------
variable "lifecycle_ia_days" {
  description = "Days before transitioning logs to Standard-IA"
  type        = number
  default     = 30
}

variable "lifecycle_glacier_days" {
  description = "Days before transitioning logs to Glacier"
  type        = number
  default     = 90
}

variable "lifecycle_expire_days" {
  description = "Days before expiring (deleting) logs"
  type        = number
  default     = 365
}

# -----------------------------------------------------------------------------
# Ingestion
# -----------------------------------------------------------------------------
variable "ingestion_lambda_concurrency" {
  description = "Reserved concurrency for the ingestion Lambda"
  type        = number
  default     = 10
}

variable "ingestion_batch_size" {
  description = "Number of documents per OpenSearch bulk request"
  type        = number
  default     = 500
}
