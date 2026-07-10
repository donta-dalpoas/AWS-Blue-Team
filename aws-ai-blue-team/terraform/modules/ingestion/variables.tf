variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the central security logs S3 bucket"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the central security logs S3 bucket"
  type        = string
}

variable "opensearch_endpoint" {
  description = "OpenSearch domain endpoint URL"
  type        = string
}

variable "opensearch_domain_arn" {
  description = "ARN of the OpenSearch domain"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key"
  type        = string
}

variable "sns_alert_topic_arn" {
  description = "ARN of the agent alerts SNS topic for alarms"
  type        = string
}

variable "lambda_concurrency" {
  description = "Reserved concurrency for ingestion Lambda"
  type        = number
  default     = 10
}

variable "batch_size" {
  description = "Number of documents per OpenSearch bulk request"
  type        = number
  default     = 500
}
