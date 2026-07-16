variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN of the security findings SNS topic to subscribe to"
  type        = string
}

variable "agent_role_arn" {
  description = "ARN of the SOC Analyst IAM role"
  type        = string
}

variable "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  type        = string
}

variable "gateway_url" {
  description = "AgentCore Gateway URL"
  type        = string
}

variable "s3_bucket_name" {
  description = "Central security logs S3 bucket name"
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
