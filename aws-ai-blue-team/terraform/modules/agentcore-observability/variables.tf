variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "sns_alert_topic_arn" {
  description = "ARN of the agent alerts SNS topic"
  type        = string
}

variable "gateway_lambda_name" {
  description = "Name of the Gateway Lambda function"
  type        = string
}

variable "evaluator_lambda_name" {
  description = "Name of the Cedar evaluator Lambda function"
  type        = string
}
