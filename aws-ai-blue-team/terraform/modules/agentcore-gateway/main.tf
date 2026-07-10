# =============================================================================
# AgentCore Gateway Module - API Gateway + Lambda Router
# =============================================================================

data "archive_file" "gateway" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/agentcore-gateway"
  output_path = "${path.module}/agentcore-gateway.zip"
}

# -----------------------------------------------------------------------------
# API Gateway (HTTP API v2)
# -----------------------------------------------------------------------------
resource "aws_apigatewayv2_api" "agentcore" {
  name          = "${var.name_prefix}-agentcore"
  protocol_type = "HTTP"
  description   = "AgentCore Gateway - MCP invocation endpoint"

  tags = {
    Name = "${var.name_prefix}-agentcore-api"
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.agentcore.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      ip               = "$context.identity.sourceIp"
      method           = "$context.httpMethod"
      path             = "$context.path"
      status           = "$context.status"
      latency          = "$context.responseLatency"
      integrationLatency = "$context.integrationLatency"
    })
  }

  tags = {
    Name = "${var.name_prefix}-agentcore-stage"
  }
}

# Lambda integration
resource "aws_apigatewayv2_integration" "gateway_lambda" {
  api_id                 = aws_apigatewayv2_api.agentcore.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.gateway.invoke_arn
  payload_format_version = "2.0"
}

# Routes
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.agentcore.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.gateway_lambda.id}"
}

resource "aws_apigatewayv2_route" "invoke" {
  api_id    = aws_apigatewayv2_api.agentcore.id
  route_key = "POST /invoke"
  target    = "integrations/${aws_apigatewayv2_integration.gateway_lambda.id}"
}

resource "aws_apigatewayv2_route" "invoke_agent" {
  api_id    = aws_apigatewayv2_api.agentcore.id
  route_key = "POST /invoke/{agent_name}"
  target    = "integrations/${aws_apigatewayv2_integration.gateway_lambda.id}"
}

resource "aws_apigatewayv2_route" "list_agents" {
  api_id    = aws_apigatewayv2_api.agentcore.id
  route_key = "GET /agents"
  target    = "integrations/${aws_apigatewayv2_integration.gateway_lambda.id}"
}

# -----------------------------------------------------------------------------
# Gateway Lambda
# -----------------------------------------------------------------------------
resource "aws_lambda_function" "gateway" {
  filename         = data.archive_file.gateway.output_path
  function_name    = "agentcore-gateway"
  role             = aws_iam_role.gateway.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.gateway.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 256
  timeout          = 29

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      POLICY_EVALUATOR_ARN = var.policy_evaluator_arn
      OPENSEARCH_ENDPOINT  = var.opensearch_endpoint
      ENVIRONMENT          = "dev"
    }
  }

  tags = {
    Name = "${var.name_prefix}-agentcore-gateway"
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.gateway.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.agentcore.execution_arn}/*/*"
}

# -----------------------------------------------------------------------------
# IAM Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "gateway" {
  name = "${var.name_prefix}-agentcore-gateway-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${var.name_prefix}-agentcore-gateway-role" }
}

resource "aws_iam_role_policy" "gateway" {
  name = "gateway-permissions"
  role = aws_iam_role.gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Access logs
resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${var.name_prefix}-agentcore"
  retention_in_days = 7

  tags = { Name = "${var.name_prefix}-api-access-logs" }
}
