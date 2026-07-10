variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the central security logs S3 bucket"
  type        = string
}

variable "opensearch_arn" {
  description = "ARN of the OpenSearch domain"
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN of the security findings SNS topic"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}
