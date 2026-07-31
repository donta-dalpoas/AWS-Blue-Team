# =============================================================================
# Executive Summary Agent - Module Outputs
# =============================================================================

output "lambda_function_name" {
  description = "Name of the Executive Summary Lambda function"
  value       = aws_lambda_function.executive_summary.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Executive Summary Lambda function"
  value       = aws_lambda_function.executive_summary.arn
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.executive_summary.arn
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge schedule rule"
  value       = aws_cloudwatch_event_rule.executive_summary_schedule.arn
}

output "log_group_name" {
  description = "CloudWatch Log Group name"
  value       = aws_cloudwatch_log_group.executive_summary.name
}
