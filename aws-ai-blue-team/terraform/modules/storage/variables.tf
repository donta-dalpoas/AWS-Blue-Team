variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for S3 encryption"
  type        = string
}

variable "lifecycle_ia_days" {
  description = "Days before transitioning to Standard-IA"
  type        = number
  default     = 30
}

variable "lifecycle_glacier_days" {
  description = "Days before transitioning to Glacier"
  type        = number
  default     = 90
}

variable "lifecycle_expire_days" {
  description = "Days before expiring objects"
  type        = number
  default     = 365
}
