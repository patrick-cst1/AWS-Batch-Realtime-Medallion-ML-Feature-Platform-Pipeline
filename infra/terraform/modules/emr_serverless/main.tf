# EMR Serverless Application
resource "aws_emrserverless_application" "main" {
  name          = "${var.project_name}-${var.environment}-app"
  release_label = var.release_label
  type          = "Spark"

  maximum_capacity {
    cpu    = "16 vCPU"
    memory = "64 GB"
  }

  auto_start_configuration {
    enabled = true
  }

  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = 15
  }

  initial_capacity {
    initial_capacity_type = "Driver"

    initial_capacity_config {
      worker_count = 1
      worker_configuration {
        cpu    = "1 vCPU"
        memory = "4 GB"
      }
    }
  }

  initial_capacity {
    initial_capacity_type = "Executor"

    initial_capacity_config {
      worker_count = 1
      worker_configuration {
        cpu    = "1 vCPU"
        memory = "4 GB"
      }
    }
  }
}

# IAM Role for EMR Serverless Job Execution
resource "aws_iam_role" "emr_job" {
  name = "${var.project_name}-${var.environment}-emr-job-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "emr-serverless.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "emr_job" {
  name = "${var.project_name}-${var.environment}-emr-job-policy"
  role = aws_iam_role.emr_job.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          var.datalake_bucket_arn,
          "${var.datalake_bucket_arn}/*",
          var.code_bucket_arn,
          "${var.code_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:BatchCreatePartition"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sagemaker:DescribeFeatureGroup",
          "sagemaker:PutRecord"
        ]
        Resource = "arn:aws:sagemaker:*:*:feature-group/${var.feature_group_name}"
      },
      {
        Effect = "Allow"
        Action = [
          "sagemaker-featurestore-runtime:BatchPutRecord",
          "sagemaker-featurestore-runtime:PutRecord"
        ]
        Resource = "arn:aws:sagemaker:*:*:feature-group/${var.feature_group_name}"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:log-group:/aws/emr-serverless/*"
      }
    ]
  })
}
