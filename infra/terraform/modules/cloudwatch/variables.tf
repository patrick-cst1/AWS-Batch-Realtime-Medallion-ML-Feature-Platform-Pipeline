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

variable "emr_application_id" {
  description = "EMR Serverless Application ID"
  type        = string
}

variable "firehose_delivery_stream_name" {
  description = "Kinesis Firehose delivery stream name"
  type        = string
}

variable "aws_region" {
  description = "AWS Region"
  type        = string
}
