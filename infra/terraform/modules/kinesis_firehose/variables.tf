variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "shard_count" {
  description = "Number of Kinesis shards"
  type        = number
  default     = 1
}

variable "datalake_bucket_name" {
  description = "Datalake S3 bucket name"
  type        = string
}

variable "datalake_bucket_arn" {
  description = "Datalake S3 bucket ARN"
  type        = string
}

variable "kms_key_id" {
  description = "KMS Key ID"
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "KMS Key ARN"
  type        = string
  default     = null
}
