output "datalake_bucket_name" {
  description = "Datalake S3 bucket name"
  value       = module.s3_datalake.bucket_name
}

output "code_bucket_name" {
  description = "Code S3 bucket name"
  value       = module.s3_datalake.code_bucket_name
}

output "kinesis_stream_name" {
  description = "Kinesis Data Stream name"
  value       = module.kinesis_firehose.stream_name
}

output "emr_application_id" {
  description = "EMR Serverless Application ID"
  value       = module.emr_serverless.application_id
}

output "emr_job_role_arn" {
  description = "EMR Serverless job execution role ARN"
  value       = module.emr_serverless.job_role_arn
}

output "feature_group_name" {
  description = "SageMaker Feature Group name"
  value       = module.sagemaker_featurestore.feature_group_name
}

output "step_function_arn" {
  description = "Step Functions state machine ARN"
  value       = module.step_functions.state_machine_arn
}

output "backfill_step_function_arn" {
  description = "Backfill Step Functions state machine ARN"
  value       = module.step_functions.backfill_state_machine_arn
}

output "glue_database_name" {
  description = "Glue Catalog database name"
  value       = module.glue.database_name
}

output "cloudwatch_dashboard_name" {
  description = "CloudWatch Dashboard name"
  value       = module.cloudwatch.dashboard_name
}
