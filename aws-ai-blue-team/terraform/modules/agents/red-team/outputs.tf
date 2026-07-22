output "lambda_arn" {
  value = aws_lambda_function.red_team.arn
}

output "lambda_name" {
  value = aws_lambda_function.red_team.function_name
}
