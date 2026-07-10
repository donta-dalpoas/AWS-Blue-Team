variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for SNS/SQS encryption"
  type        = string
}
