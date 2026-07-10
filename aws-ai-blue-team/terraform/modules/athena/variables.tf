variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the central security logs S3 bucket"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "active_regions" {
  description = "List of active AWS regions"
  type        = list(string)
  default     = ["us-east-1", "us-west-2"]
}
