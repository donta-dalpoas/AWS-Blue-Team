output "gateway_url" {
  description = "AgentCore Gateway endpoint URL"
  value       = aws_apigatewayv2_api.agentcore.api_endpoint
}

output "lambda_name" {
  description = "Name of the Gateway Lambda function"
  value       = aws_lambda_function.gateway.function_name
}

output "lambda_arn" {
  description = "ARN of the Gateway Lambda function"
  value       = aws_lambda_function.gateway.arn
}

output "api_id" {
  description = "ID of the API Gateway"
  value       = aws_apigatewayv2_api.agentcore.id
}
