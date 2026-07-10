output "sqs_queue_arn" {
  description = "ARN of the ingestion SQS queue"
  value       = aws_sqs_queue.ingestion.arn
}

output "sqs_queue_url" {
  description = "URL of the ingestion SQS queue"
  value       = aws_sqs_queue.ingestion.url
}

output "lambda_arn" {
  description = "ARN of the log ingestor Lambda"
  value       = aws_lambda_function.log_ingestor.arn
}

output "lambda_name" {
  description = "Name of the log ingestor Lambda"
  value       = aws_lambda_function.log_ingestor.function_name
}
