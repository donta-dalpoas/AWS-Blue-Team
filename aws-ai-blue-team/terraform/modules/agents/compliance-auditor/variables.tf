variable "name_prefix" {
  type = string
}

variable "agent_role_arn" {
  type = string
}

variable "s3_bucket_name" {
  type = string
}

variable "opensearch_endpoint" {
  type = string
}

variable "slack_webhook_url" {
  type    = string
  default = ""
}
