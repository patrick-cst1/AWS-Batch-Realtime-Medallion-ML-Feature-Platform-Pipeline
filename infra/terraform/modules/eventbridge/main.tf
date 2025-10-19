# IAM Role for EventBridge to invoke Step Functions
resource "aws_iam_role" "eventbridge" {
  name = "${var.project_name}-${var.environment}-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge" {
  name = "${var.project_name}-${var.environment}-eventbridge-policy"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = var.state_machine_arn
      }
    ]
  })
}

# EventBridge Rule for Stream Pipeline (every N minutes)
resource "aws_cloudwatch_event_rule" "stream" {
  name                = "${var.project_name}-${var.environment}-stream-trigger"
  description         = "Trigger stream pipeline every ${var.stream_schedule_minutes} minutes"
  schedule_expression = "rate(${var.stream_schedule_minutes} minutes)"
}

resource "aws_cloudwatch_event_target" "stream" {
  rule      = aws_cloudwatch_event_rule.stream.name
  target_id = "StreamPipeline"
  arn       = var.state_machine_arn
  role_arn  = aws_iam_role.eventbridge.arn

  input = jsonencode({
    mode         = "stream"
    now          = "$.time"
    bucket       = var.datalake_bucket_name
    codeBucket   = var.code_bucket_name
    bronzePrefix = "bronze/streaming"
    silverPrefix = "silver"
    goldPrefix   = "gold"
    featureGroup = var.feature_group_name
    emr = {
      appId   = var.emr_application_id
      jobRole = var.emr_job_role_arn
    }
  })
}

# EventBridge Rule for Daily Pipeline
resource "aws_cloudwatch_event_rule" "daily" {
  name                = "${var.project_name}-${var.environment}-daily-trigger"
  description         = "Trigger daily dataset build pipeline"
  schedule_expression = var.daily_schedule_cron
}

resource "aws_cloudwatch_event_target" "daily" {
  rule      = aws_cloudwatch_event_rule.daily.name
  target_id = "DailyPipeline"
  arn       = var.state_machine_arn
  role_arn  = aws_iam_role.eventbridge.arn

  input = jsonencode({
    mode             = "daily"
    bucket           = var.datalake_bucket_name
    codeBucket       = var.code_bucket_name
    goldPrefix       = "gold"
    trainingPrefix   = "gold/training"
    inferencePrefix  = "gold/inference"
    featureGroup     = var.feature_group_name
    emr = {
      appId   = var.emr_application_id
      jobRole = var.emr_job_role_arn
    }
    glue = {
      crawlerName = "${var.project_name}-${var.environment}-gold-crawler"
    }
  })
}
