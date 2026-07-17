output "lambda_arn" {
  description = "ARN of the IR Agent Lambda"
  value       = aws_lambda_function.incident_responder.arn
}

output "lambda_name" {
  description = "Name of the IR Agent Lambda"
  value       = aws_lambda_function.incident_responder.function_name
}

output "slack_handler_arn" {
  description = "ARN of the Slack approval handler Lambda"
  value       = aws_lambda_function.slack_approval_handler.arn
}

output "pending_approvals_table" {
  description = "Name of the DynamoDB pending approvals table"
  value       = aws_dynamodb_table.pending_approvals.name
}

output "dlq_arn" {
  description = "ARN of the IR Agent dead-letter queue"
  value       = aws_sqs_queue.ir_agent_dlq.arn
}
