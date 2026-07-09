output "state_bucket_name" {
  description = "Name of the S3 bucket storing Terraform state"
  value       = aws_s3_bucket.terraform_state.id
}

output "state_bucket_arn" {
  description = "ARN of the S3 bucket storing Terraform state"
  value       = aws_s3_bucket.terraform_state.arn
}

output "lock_table_name" {
  description = "Name of the DynamoDB table used for state locking"
  value       = aws_dynamodb_table.terraform_lock.name
}

output "lock_table_arn" {
  description = "ARN of the DynamoDB table used for state locking"
  value       = aws_dynamodb_table.terraform_lock.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}

output "plan_role_arn" {
  description = "ARN of the IAM role used by GitHub Actions for terraform plan"
  value       = aws_iam_role.github_actions_plan.arn
}

output "apply_role_arn" {
  description = "ARN of the IAM role used by GitHub Actions for terraform apply"
  value       = aws_iam_role.github_actions_apply.arn
}
