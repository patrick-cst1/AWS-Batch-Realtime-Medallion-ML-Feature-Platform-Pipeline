output "application_id" {
  description = "EMR Serverless Application ID"
  value       = aws_emrserverless_application.main.id
}

output "application_arn" {
  description = "EMR Serverless Application ARN"
  value       = aws_emrserverless_application.main.arn
}

output "job_role_arn" {
  description = "EMR Serverless job execution role ARN"
  value       = aws_iam_role.emr_job.arn
}
