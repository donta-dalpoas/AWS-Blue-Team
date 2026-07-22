output "lambda_arn" {
  value = aws_lambda_function.threat_hunter.arn
}

output "lambda_name" {
  value = aws_lambda_function.threat_hunter.function_name
}
