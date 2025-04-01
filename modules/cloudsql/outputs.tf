output "instance_connection_name" {
  description = "The connection name used by the Cloud SQL Proxy."
  value       = google_sql_database_instance.poster_db_instance.connection_name
}
