output "endpoint" {
  description = "OpenSearch domain endpoint URL"
  value       = aws_opensearch_domain.security.endpoint
}

output "domain_arn" {
  description = "ARN of the OpenSearch domain"
  value       = aws_opensearch_domain.security.arn
}

output "domain_name" {
  description = "Name of the OpenSearch domain"
  value       = aws_opensearch_domain.security.domain_name
}

output "kibana_endpoint" {
  description = "OpenSearch Dashboards endpoint"
  value       = aws_opensearch_domain.security.dashboard_endpoint
}
