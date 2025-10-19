# IAM Role for SageMaker Feature Store
resource "aws_iam_role" "featurestore" {
  name = "${var.project_name}-${var.environment}-featurestore-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "featurestore" {
  name = "${var.project_name}-${var.environment}-featurestore-policy"
  role = aws_iam_role.featurestore.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.datalake_bucket_name}",
          "arn:aws:s3:::${var.datalake_bucket_name}/feature-store/*"
        ]
      }
    ]
  })
}

# SageMaker Feature Group
resource "aws_sagemaker_feature_group" "main" {
  feature_group_name             = var.feature_group_name
  record_identifier_feature_name = "card_id"
  event_time_feature_name        = "event_time"
  role_arn                       = aws_iam_role.featurestore.arn

  feature_definition {
    feature_name = "card_id"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "event_time"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "event_id"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "merchant_id"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "amount"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "currency"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "country"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "pos_mode"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "txn_count_1h"
    feature_type = "Integral"
  }

  feature_definition {
    feature_name = "txn_amount_1h"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "merchant_count_24h"
    feature_type = "Integral"
  }

  feature_definition {
    feature_name = "avg_amount_7d"
    feature_type = "Fractional"
  }

  online_store_config {
    enable_online_store = true
  }

  offline_store_config {
    s3_storage_config {
      s3_uri     = "s3://${var.datalake_bucket_name}/feature-store/offline"
    }
  }
}
