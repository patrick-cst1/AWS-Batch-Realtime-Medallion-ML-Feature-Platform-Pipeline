# Glue Catalog Database
resource "aws_glue_catalog_database" "main" {
  name = "${var.project_name}_${var.environment}_db"
}

# IAM Role for Glue Crawler
resource "aws_iam_role" "crawler" {
  name = "${var.project_name}-${var.environment}-crawler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "crawler_service" {
  role       = aws_iam_role.crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "crawler" {
  name = "${var.project_name}-${var.environment}-crawler-policy"
  role = aws_iam_role.crawler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.datalake_bucket_arn,
          "${var.datalake_bucket_arn}/*"
        ]
      },
      
    ]
  })
}

# Glue Crawler for Silver Layer
resource "aws_glue_crawler" "silver" {
  name          = "${var.project_name}-${var.environment}-silver-crawler"
  role          = aws_iam_role.crawler.arn
  database_name = aws_glue_catalog_database.main.name

  s3_target {
    path = "s3://${var.datalake_bucket_name}/silver/"
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
    }
  })
}

# Glue Crawler for Gold Layer
resource "aws_glue_crawler" "gold" {
  name          = "${var.project_name}-${var.environment}-gold-crawler"
  role          = aws_iam_role.crawler.arn
  database_name = aws_glue_catalog_database.main.name

  s3_target {
    path = "s3://${var.datalake_bucket_name}/gold/"
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
    }
  })
}
