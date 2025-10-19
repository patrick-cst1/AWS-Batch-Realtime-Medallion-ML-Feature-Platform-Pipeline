output "stream_rule_name" {
  description = "EventBridge stream rule name"
  value       = aws_cloudwatch_event_rule.stream.name
}

output "daily_rule_name" {
  description = "EventBridge daily rule name"
  value       = aws_cloudwatch_event_rule.daily.name
}
