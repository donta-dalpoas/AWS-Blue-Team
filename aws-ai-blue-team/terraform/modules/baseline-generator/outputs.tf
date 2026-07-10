output "lambda_arn" {
  description = "ARN of the baseline generator Lambda"
  value       = aws_lambda_function.baseline_generator.arn
}

output "lambda_name" {
  description = "Name of the baseline generator Lambda"
  value       = aws_lambda_function.baseline_generator.function_name
}

output "schedule_arn" {
  description = "ARN of the EventBridge schedule rule"
  value       = aws_cloudwatch_event_rule.baseline_weekly.arn
}
