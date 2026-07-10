output "bucket_name" {
  description = "Name of the security logs S3 bucket"
  value       = aws_s3_bucket.security_logs.id
}

output "bucket_arn" {
  description = "ARN of the security logs S3 bucket"
  value       = aws_s3_bucket.security_logs.arn
}

output "bucket_id" {
  description = "ID of the security logs S3 bucket"
  value       = aws_s3_bucket.security_logs.id
}
