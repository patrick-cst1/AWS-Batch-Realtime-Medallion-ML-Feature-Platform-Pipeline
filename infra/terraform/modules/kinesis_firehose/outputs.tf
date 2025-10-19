output "stream_name" {
  description = "Kinesis Data Stream name"
  value       = aws_kinesis_stream.main.name
}

output "stream_arn" {
  description = "Kinesis Data Stream ARN"
  value       = aws_kinesis_stream.main.arn
}

output "firehose_name" {
  description = "Kinesis Firehose Delivery Stream name"
  value       = aws_kinesis_firehose_delivery_stream.main.name
}

output "firehose_arn" {
  description = "Kinesis Firehose Delivery Stream ARN"
  value       = aws_kinesis_firehose_delivery_stream.main.arn
}
