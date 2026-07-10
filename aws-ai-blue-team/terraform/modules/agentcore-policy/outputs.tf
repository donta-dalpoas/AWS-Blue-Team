output "evaluator_lambda_arn" {
  description = "ARN of the Cedar evaluator Lambda"
  value       = aws_lambda_function.cedar_evaluator.arn
}

output "evaluator_lambda_name" {
  description = "Name of the Cedar evaluator Lambda"
  value       = aws_lambda_function.cedar_evaluator.function_name
}

output "policy_bucket_name" {
  description = "Name of the Cedar policy S3 bucket"
  value       = aws_s3_bucket.cedar_policies.id
}
