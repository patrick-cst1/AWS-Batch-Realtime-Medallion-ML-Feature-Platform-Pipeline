variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "datalake_bucket_name" {
  description = "Datalake S3 bucket name"
  type        = string
}

variable "datalake_bucket_arn" {
  description = "Datalake S3 bucket ARN"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS Key ARN"
  type        = string
  default     = null
}
