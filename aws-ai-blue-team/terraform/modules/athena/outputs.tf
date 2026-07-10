output "database_name" {
  description = "Name of the Glue database"
  value       = aws_glue_catalog_database.security_logs.name
}

output "workgroup_name" {
  description = "Name of the Athena workgroup"
  value       = aws_athena_workgroup.security_analytics.name
}

output "cloudtrail_table_name" {
  description = "Name of the CloudTrail Glue table"
  value       = aws_glue_catalog_table.cloudtrail_logs.name
}

output "vpc_flow_logs_table_name" {
  description = "Name of the VPC Flow Logs Glue table"
  value       = aws_glue_catalog_table.vpc_flow_logs.name
}
