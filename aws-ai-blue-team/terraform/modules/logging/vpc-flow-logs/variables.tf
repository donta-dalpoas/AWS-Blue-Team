variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket for flow log delivery"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for flow log delivery"
  type        = string
}

variable "vpc_ids" {
  description = "List of VPC IDs to enable flow logs on"
  type        = list(string)
  default     = []
}
