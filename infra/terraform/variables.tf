variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "aws-batch-realtime-medallion"
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "emr_release_label" {
  description = "EMR Serverless release label"
  type        = string
  default     = "emr-6.15.0"
}

variable "kinesis_shard_count" {
  description = "Number of Kinesis shards"
  type        = number
  default     = 1
}

variable "s3_lifecycle_days" {
  description = "S3 lifecycle retention days"
  type        = number
  default     = 30
}

variable "stream_pipeline_schedule_minutes" {
  description = "Stream pipeline schedule in minutes"
  type        = number
  default     = 60
}

variable "daily_pipeline_schedule_cron" {
  description = "Daily pipeline schedule cron expression (UTC)"
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "feature_group_name" {
  description = "SageMaker Feature Group name"
  type        = string
  default     = "rt_card_features_v1"
}
