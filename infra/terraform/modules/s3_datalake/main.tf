# Datalake Bucket
resource "aws_s3_bucket" "datalake" {
  bucket = "${var.project_name}-${var.environment}-datalake-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    id     = "bronze-lifecycle"
    status = "Enabled"

    filter {
      prefix = "bronze/"
    }

    expiration {
      days = var.lifecycle_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }

  rule {
    id     = "logs-lifecycle"
    status = "Enabled"

    filter {
      prefix = "logs/"
    }

    expiration {
      days = var.lifecycle_days
    }
  }
}

# Code Bucket
resource "aws_s3_bucket" "code" {
  bucket = "${var.project_name}-${var.environment}-code-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "code" {
  bucket = aws_s3_bucket.code.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "code" {
  bucket = aws_s3_bucket.code.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "code" {
  bucket = aws_s3_bucket.code.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_caller_identity" "current" {}
