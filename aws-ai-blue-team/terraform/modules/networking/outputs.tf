output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "opensearch_sg_id" {
  description = "Security group ID for OpenSearch"
  value       = aws_security_group.opensearch.id
}

output "lambda_sg_id" {
  description = "Security group ID for Lambda functions"
  value       = aws_security_group.lambda.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}
