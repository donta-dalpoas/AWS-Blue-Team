output "securityhub_arn" {
  description = "ARN of the SecurityHub account"
  value       = aws_securityhub_account.main.arn
}
