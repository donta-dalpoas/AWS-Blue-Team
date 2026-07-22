variable "aws_region" {
  description = "Primary AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "account_id" {
  description = "AWS Account ID (used in resource naming for global uniqueness)"
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Account ID must be a 12-digit number."
  }
}

variable "github_org" {
  description = "GitHub organization name (e.g., 'my-org')"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (e.g., 'aws-ai-blue-team')"
  type        = string
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
  description = "Project name used for tagging and resource naming"
  type        = string
  default     = "aws-ai-blue-team"
}
