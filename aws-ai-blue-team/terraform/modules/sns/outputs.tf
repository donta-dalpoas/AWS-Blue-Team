output "findings_topic_arn" {
  description = "ARN of the security findings SNS topic"
  value       = aws_sns_topic.security_findings.arn
}

output "findings_topic_name" {
  description = "Name of the security findings SNS topic"
  value       = aws_sns_topic.security_findings.name
}

output "alert_topic_arn" {
  description = "ARN of the agent alerts SNS topic"
  value       = aws_sns_topic.agent_alerts.arn
}

output "alert_topic_name" {
  description = "Name of the agent alerts SNS topic"
  value       = aws_sns_topic.agent_alerts.name
}
