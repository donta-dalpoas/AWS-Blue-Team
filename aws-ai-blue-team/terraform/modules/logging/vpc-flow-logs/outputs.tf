output "flow_log_ids" {
  description = "List of Flow Log IDs"
  value       = aws_flow_log.vpc[*].id
}
