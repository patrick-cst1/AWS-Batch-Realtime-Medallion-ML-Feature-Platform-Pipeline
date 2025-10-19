terraform {
  backend "s3" {
    # Backend configuration should be provided via -backend-config flags or backend.hcl
    # Example:
    # bucket         = "your-terraform-state-bucket"
    # key            = "aws-batch-realtime-medallion/terraform.tfstate"
    # region         = "ap-southeast-1"
    # dynamodb_table = "terraform-state-lock"
    # encrypt        = true
  }
}
