provider "google" {
  project = var.project_id
  region  = var.region
}

module "cloudsql" {
  source              = "./modules/cloudsql"
  region              = var.region
  authorized_networks = var.authorized_networks
}
