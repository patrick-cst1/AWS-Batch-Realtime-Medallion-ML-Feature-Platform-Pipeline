variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "kms_key_id" {
  description = "KMS Key ID for S3 encryption"
  type        = string
  default     = null
}

variable "lifecycle_days" {
  description = "Number of days for lifecycle retention"
  type        = number
  default     = 30
}
