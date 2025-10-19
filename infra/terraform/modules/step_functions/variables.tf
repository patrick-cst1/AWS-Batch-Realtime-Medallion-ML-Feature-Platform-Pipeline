variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
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

variable "glue_database_name" {
  description = "Glue Catalog database name"
  type        = string
}

variable "glue_crawler_name" {
  description = "Glue Crawler name for Gold layer"
  type        = string
}
