# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/States", "ExecutionsFailed", { stat = "Sum", label = "SFN Executions Failed" }],
            [".", "ExecutionsSucceeded", { stat = "Sum", label = "SFN Executions Succeeded" }],
            [".", "ExecutionsTimedOut", { stat = "Sum", label = "SFN Executions Timed Out" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Step Functions Executions"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Kinesis/Firehose", "DeliveryToS3.Success", { stat = "Sum", label = "Firehose Success" }],
            [".", "DeliveryToS3.DataFreshness", { stat = "Average", label = "Data Freshness (sec)" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Kinesis Firehose Delivery"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["P1Unified", "StreamPipelineSuccess", { stat = "Sum", label = "Stream Pipeline Success" }],
            [".", "DailyPipelineSuccess", { stat = "Sum", label = "Daily Pipeline Success" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Custom Pipeline Metrics"
        }
      },
      {
        type = "log"
        properties = {
          query   = "SOURCE '/aws/vendedlogs/states/${var.project_name}-${var.environment}-stream-pipeline' | fields @timestamp, @message | sort @timestamp desc | limit 20"
          region  = var.aws_region
          title   = "Recent Step Functions Logs"
        }
      }
    ]
  })
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "sfn_failed" {
  alarm_name          = "${var.project_name}-${var.environment}-sfn-execution-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when Step Functions execution fails"
  treat_missing_data  = "notBreaching"

  dimensions = {
    StateMachineArn = var.state_machine_arn
  }
}

resource "aws_cloudwatch_metric_alarm" "firehose_failed" {
  alarm_name          = "${var.project_name}-${var.environment}-firehose-delivery-failed"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DeliveryToS3.Success"
  namespace           = "AWS/Kinesis/Firehose"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.95"
  alarm_description   = "Alert when Firehose delivery success rate drops below 95%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DeliveryStreamName = var.firehose_delivery_stream_name
  }
}
