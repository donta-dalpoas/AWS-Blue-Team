output "dashboard_name" {
  description = "Name of the AgentCore CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.agentcore.dashboard_name
}
