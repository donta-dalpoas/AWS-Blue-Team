variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for CloudTrail logs"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for CloudTrail encryption"
  type        = string
}
