output "dashboard_name" {
  description = "CloudWatch Dashboard name"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "sfn_alarm_arn" {
  description = "Step Functions failure alarm ARN"
  value       = aws_cloudwatch_metric_alarm.sfn_failed.arn
}

output "firehose_alarm_arn" {
  description = "Firehose failure alarm ARN"
  value       = aws_cloudwatch_metric_alarm.firehose_failed.arn
}
