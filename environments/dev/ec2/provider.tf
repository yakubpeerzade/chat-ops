provider "aws" {
  region = var.region

  default_tags {
    tags = {
      managed_by = "chat-ops"
      terraform  = "true"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}