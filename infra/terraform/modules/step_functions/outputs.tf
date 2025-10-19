output "state_machine_arn" {
  description = "Step Functions state machine ARN"
  value       = aws_sfn_state_machine.stream_pipeline.arn
}

output "state_machine_name" {
  description = "Step Functions state machine name"
  value       = aws_sfn_state_machine.stream_pipeline.name
}

output "state_machine_role_arn" {
  description = "Step Functions state machine role ARN"
  value       = aws_iam_role.sfn.arn
}
