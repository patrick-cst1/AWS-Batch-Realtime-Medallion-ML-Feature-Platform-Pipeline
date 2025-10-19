variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "state_machine_arn" {
  description = "Step Functions state machine ARN"
  type        = string
}

variable "step_function_role_arn" {
  description = "Step Functions role ARN"
  type        = string
}

variable "stream_schedule_minutes" {
  description = "Stream pipeline schedule in minutes"
  type        = number
  default     = 10
}

variable "daily_schedule_cron" {
  description = "Daily pipeline schedule cron expression"
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "emr_application_id" {
  description = "EMR Serverless Application ID"
  type        = string
}

variable "emr_job_role_arn" {
  description = "EMR Serverless job execution role ARN"
  type        = string
}

variable "datalake_bucket_name" {
  description = "Datalake S3 bucket name"
  type        = string
}

variable "code_bucket_name" {
  description = "Code S3 bucket name"
  type        = string
}

variable "feature_group_name" {
  description = "SageMaker Feature Group name"
  type        = string
}
