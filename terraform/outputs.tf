# =============================================================================
# Root Module Outputs
# =============================================================================
# These outputs are consumed by downstream epics (agents) and documented
# in docs/architecture.md.

# Uncomment as modules are implemented:

# output "s3_bucket_name" {
#   description = "Central security logs S3 bucket name"
#   value       = module.storage.bucket_name
# }

# output "opensearch_endpoint" {
#   description = "OpenSearch domain endpoint URL"
#   value       = module.opensearch.endpoint
# }

# output "sns_findings_topic_arn" {
#   description = "SNS topic ARN for security findings"
#   value       = module.sns.findings_topic_arn
# }

# output "agentcore_gateway_url" {
#   description = "AgentCore Gateway MCP endpoint URL"
#   value       = module.agentcore_gateway.gateway_url
# }

# output "agent_role_arns" {
#   description = "Map of agent name to IAM role ARN"
#   value       = module.agentcore_identity.agent_role_arns
# }
