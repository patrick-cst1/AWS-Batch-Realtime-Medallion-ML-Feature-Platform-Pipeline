output "database_name" {
  description = "Glue Catalog database name"
  value       = aws_glue_catalog_database.main.name
}

output "silver_crawler_name" {
  description = "Silver crawler name"
  value       = aws_glue_crawler.silver.name
}

output "gold_crawler_name" {
  description = "Gold crawler name"
  value       = aws_glue_crawler.gold.name
}
