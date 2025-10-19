variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "feature_group_name" {
  description = "SageMaker Feature Group name"
  type        = string
}

variable "datalake_bucket_name" {
  description = "Datalake S3 bucket name"
  type        = string
}

variable "kms_key_id" {
  description = "KMS Key ID"
  type        = string
  default     = null
}
