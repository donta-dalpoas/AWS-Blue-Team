variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "agent_role_arn" {
  description = "ARN of the Incident Responder IAM role"
  type        = string
}

variable "s3_bucket_name" {
  description = "Central security logs S3 bucket name"
  type        = string
}

variable "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  type        = string
}

variable "cedar_evaluator_arn" {
  description = "ARN of the Cedar policy evaluator Lambda"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for encryption"
  type        = string
}

variable "sns_alert_topic_arn" {
  description = "SNS topic ARN for agent operational alerts"
  type        = string
}

variable "api_gateway_id" {
  description = "ID of the AgentCore API Gateway"
  type        = string
}

variable "api_gateway_execution_arn" {
  description = "Execution ARN of the AgentCore API Gateway"
  type        = string
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for approval messages (empty string to disable)"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repo for issue creation (format: owner/repo)"
  type        = string
  default     = "donta-dalpoas/AWS-Blue-Team"
}
