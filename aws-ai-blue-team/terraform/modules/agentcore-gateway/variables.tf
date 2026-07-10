variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "policy_evaluator_arn" {
  description = "ARN of the Cedar policy evaluator Lambda"
  type        = string
}

variable "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  type        = string
}
