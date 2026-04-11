terraform {
  backend "s3" {
    bucket         = "chat-ops-tfstate-s3"
    key            = "dev/${var.request_id}/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "chat-ops-tf-lock"
  }
}