output "lambda_arn" {
  description = "ARN of the SOC Analyst Agent Lambda"
  value       = aws_lambda_function.soc_analyst.arn
}

output "lambda_name" {
  description = "Name of the SOC Analyst Agent Lambda"
  value       = aws_lambda_function.soc_analyst.function_name
}

output "dlq_arn" {
  description = "ARN of the SOC Agent dead-letter queue"
  value       = aws_sqs_queue.soc_agent_dlq.arn
}
