# IAM Role for Step Functions
resource "aws_iam_role" "sfn" {
  name = "${var.project_name}-${var.environment}-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "sfn" {
  name = "${var.project_name}-${var.environment}-sfn-policy"
  role = aws_iam_role.sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "emr-serverless:StartJobRun",
          "emr-serverless:GetJobRun",
          "emr-serverless:CancelJobRun"
        ]
        Resource = [
          "arn:aws:emr-serverless:*:*:/applications/${var.emr_application_id}",
          "arn:aws:emr-serverless:*:*:/applications/${var.emr_application_id}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = var.emr_job_role_arn
        Condition = {
          StringLike = {
            "iam:PassedToService" = "emr-serverless.amazonaws.com"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "glue:StartCrawler",
          "glue:GetCrawler"
        ]
        Resource = [
          "arn:aws:glue:*:*:crawler/${var.glue_crawler_name}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.datalake_bucket_name}",
          "arn:aws:s3:::${var.datalake_bucket_name}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutLogEvents",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch Log Group for Step Functions
resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/vendedlogs/states/${var.project_name}-${var.environment}-stream-pipeline"
  retention_in_days = 7
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "stream_pipeline" {
  name     = "${var.project_name}-${var.environment}-stream-pipeline"
  role_arn = aws_iam_role.sfn.arn

  definition = templatefile("${path.root}/../../state_machines/stream_pipeline.asl.json", {
    emr_job_role_arn   = var.emr_job_role_arn,
    emr_application_id = var.emr_application_id
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tracing_configuration {
    enabled = true
  }
}
