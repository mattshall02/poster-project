variable "project_id" {
  description = "The ID of the GCP project."
  type        = string
  default     = "the-flat-file"
}

variable "region" {
  description = "The GCP region for the resources."
  type        = string
  default     = "us-central1"
}

variable "authorized_networks" {
  description = "List of authorized networks (CIDRs) allowed to access Cloud SQL."
  type        = list(object({
    name  = string,
    value = string
  }))
  default = [
    {
      name  = "local"
      value = "47.132.240.106/32"  # Replace with your actual IP
    }
  ]
}
