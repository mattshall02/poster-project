variable "region" {
  description = "The region where the Cloud SQL instance will be deployed."
  type        = string
}

variable "authorized_networks" {
  description = "List of authorized networks (CIDR blocks) allowed to access the Cloud SQL instance."
  type        = list(object({
    name  = string,
    value = string
  }))
  default = []
}
