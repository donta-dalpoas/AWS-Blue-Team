variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "instance_type" {
  description = "OpenSearch instance type"
  type        = string
  default     = "t3.medium.search"
}

variable "instance_count" {
  description = "Number of data nodes"
  type        = number
  default     = 2
}

variable "ebs_volume_size" {
  description = "EBS volume size in GB per node"
  type        = number
  default     = 100
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for encryption at rest"
  type        = string
}

variable "vpc_subnet_ids" {
  description = "Subnet IDs for VPC deployment (empty list for public)"
  type        = list(string)
  default     = []
}

variable "vpc_security_group_id" {
  description = "Security group ID for VPC deployment"
  type        = string
  default     = ""
}

variable "master_user_name" {
  description = "Master user name for OpenSearch"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "master_user_password" {
  description = "Master user password for OpenSearch"
  type        = string
  default     = "ChangeMe123!"
  sensitive   = true
}
