variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "release_label" {
  description = "EMR Serverless release label"
  type        = string
  default     = "emr-6.15.0"
}

variable "datalake_bucket_name" {
  description = "Datalake S3 bucket name"
  type        = string
}

variable "datalake_bucket_arn" {
  description = "Datalake S3 bucket ARN"
  type        = string
}

variable "code_bucket_name" {
  description = "Code S3 bucket name"
  type        = string
}

variable "code_bucket_arn" {
  description = "Code S3 bucket ARN"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS Key ARN"
  type        = string
  default     = null
}

variable "feature_group_name" {
  description = "SageMaker Feature Group name"
  type        = string
}
