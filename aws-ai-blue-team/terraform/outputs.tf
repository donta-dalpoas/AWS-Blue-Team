# =============================================================================
# Root Module Outputs
# =============================================================================

output "s3_bucket_name" {
  description = "Central security logs S3 bucket name"
  value       = module.storage.bucket_name
}

output "s3_bucket_arn" {
  description = "Central security logs S3 bucket ARN"
  value       = module.storage.bucket_arn
}

output "kms_key_arn" {
  description = "Shared KMS key ARN"
  value       = module.kms.key_arn
}

output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint URL"
  value       = module.opensearch.endpoint
}

output "sns_findings_topic_arn" {
  description = "SNS topic ARN for security findings"
  value       = module.sns.findings_topic_arn
}

output "sns_alert_topic_arn" {
  description = "SNS topic ARN for agent alerts"
  value       = module.sns.alert_topic_arn
}

output "agentcore_gateway_url" {
  description = "AgentCore Gateway MCP endpoint URL"
  value       = module.agentcore_gateway.gateway_url
}

output "agent_role_arns" {
  description = "Map of agent name to IAM role ARN"
  value       = module.agentcore_identity.agent_role_arns
}

output "vpc_id" {
  description = "VPC ID (if created)"
  value       = var.create_vpc ? module.networking[0].vpc_id : ""
}

output "athena_workgroup" {
  description = "Athena workgroup name"
  value       = module.athena.workgroup_name
}

output "cedar_policy_bucket" {
  description = "S3 bucket for Cedar policies"
  value       = module.agentcore_policy.policy_bucket_name
}
