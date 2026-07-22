output "lambda_arn" {
  value = aws_lambda_function.compliance_auditor.arn
}

output "lambda_name" {
  value = aws_lambda_function.compliance_auditor.function_name
}
