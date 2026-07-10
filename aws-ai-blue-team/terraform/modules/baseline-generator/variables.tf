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

variable "kms_key_arn" {
  description = "ARN of the KMS key"
  type        = string
}

variable "sns_alert_topic_arn" {
  description = "ARN of the agent alerts SNS topic"
  type        = string
}

variable "active_regions" {
  description = "List of active AWS regions to scan"
  type        = list(string)
  default     = ["us-east-1", "us-west-2"]
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}
