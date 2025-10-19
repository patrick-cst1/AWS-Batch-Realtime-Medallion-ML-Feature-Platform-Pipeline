# S3 Datalake Module
module "s3_datalake" {
  source = "./modules/s3_datalake"

  project_name      = var.project_name
  environment       = var.environment
  lifecycle_days    = var.s3_lifecycle_days
}

# Kinesis + Firehose Module
module "kinesis_firehose" {
  source = "./modules/kinesis_firehose"

  project_name          = var.project_name
  environment           = var.environment
  shard_count           = var.kinesis_shard_count
  datalake_bucket_name  = module.s3_datalake.bucket_name
  datalake_bucket_arn   = module.s3_datalake.bucket_arn
}

# EMR Serverless Module
module "emr_serverless" {
  source = "./modules/emr_serverless"

  project_name          = var.project_name
  environment           = var.environment
  release_label         = var.emr_release_label
  datalake_bucket_name  = module.s3_datalake.bucket_name
  datalake_bucket_arn   = module.s3_datalake.bucket_arn
  code_bucket_name      = module.s3_datalake.code_bucket_name
  code_bucket_arn       = module.s3_datalake.code_bucket_arn
  feature_group_name    = var.feature_group_name
}

# Glue Module
module "glue" {
  source = "./modules/glue"

  project_name          = var.project_name
  environment           = var.environment
  datalake_bucket_name  = module.s3_datalake.bucket_name
  datalake_bucket_arn   = module.s3_datalake.bucket_arn
}

# SageMaker Feature Store Module
module "sagemaker_featurestore" {
  source = "./modules/sagemaker_featurestore"

  project_name          = var.project_name
  environment           = var.environment
  feature_group_name    = var.feature_group_name
  datalake_bucket_name  = module.s3_datalake.bucket_name
}

# Step Functions Module
module "step_functions" {
  source = "./modules/step_functions"

  project_name            = var.project_name
  environment             = var.environment
  emr_application_id      = module.emr_serverless.application_id
  emr_job_role_arn        = module.emr_serverless.job_role_arn
  datalake_bucket_name    = module.s3_datalake.bucket_name
  code_bucket_name        = module.s3_datalake.code_bucket_name
  feature_group_name      = var.feature_group_name
  glue_database_name      = module.glue.database_name
  glue_crawler_name       = module.glue.gold_crawler_name
}

# EventBridge Module
module "eventbridge" {
  source = "./modules/eventbridge"

  project_name                      = var.project_name
  environment                       = var.environment
  state_machine_arn                 = module.step_functions.state_machine_arn
  step_function_role_arn            = module.step_functions.state_machine_role_arn
  stream_schedule_minutes           = var.stream_pipeline_schedule_minutes
  daily_schedule_cron               = var.daily_pipeline_schedule_cron
  emr_application_id                = module.emr_serverless.application_id
  emr_job_role_arn                  = module.emr_serverless.job_role_arn
  datalake_bucket_name              = module.s3_datalake.bucket_name
  code_bucket_name                  = module.s3_datalake.code_bucket_name
  feature_group_name                = var.feature_group_name
}

# CloudWatch Module
module "cloudwatch" {
  source = "./modules/cloudwatch"

  project_name            = var.project_name
  environment             = var.environment
  state_machine_arn       = module.step_functions.state_machine_arn
  emr_application_id      = module.emr_serverless.application_id
  firehose_delivery_stream_name = module.kinesis_firehose.firehose_name
  aws_region              = var.aws_region
}
