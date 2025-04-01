resource "google_sql_database_instance" "poster_db_instance" {
  name             = "poster-db"
  database_version = "POSTGRES_13"
  region           = var.region

  deletion_protection = false  # Add this line to disable deletion protection

  settings {
    tier = "db-f1-micro"  # Adjust based on your needs
    backup_configuration {
      enabled    = true
      start_time = "03:00"  # Backup during low-activity hours
    }
    ip_configuration {
      ipv4_enabled = true

      dynamic "authorized_networks" {
        for_each = var.authorized_networks
        content {
          name  = authorized_networks.value.name
          value = authorized_networks.value.value
        }
      }
    }
  }
}

resource "google_sql_database" "posterdb" {
  name     = "posterdb"
  instance = google_sql_database_instance.poster_db_instance.name
}
