output "bucket_name" {
  description = "Datalake bucket name"
  value       = aws_s3_bucket.datalake.id
}

output "bucket_arn" {
  description = "Datalake bucket ARN"
  value       = aws_s3_bucket.datalake.arn
}

output "code_bucket_name" {
  description = "Code bucket name"
  value       = aws_s3_bucket.code.id
}

output "code_bucket_arn" {
  description = "Code bucket ARN"
  value       = aws_s3_bucket.code.arn
}
