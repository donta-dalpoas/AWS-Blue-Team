output "key_arn" {
  description = "ARN of the KMS key"
  value       = aws_kms_key.security.arn
}

output "key_id" {
  description = "ID of the KMS key"
  value       = aws_kms_key.security.key_id
}

output "key_alias_arn" {
  description = "ARN of the KMS key alias"
  value       = aws_kms_alias.security.arn
}
