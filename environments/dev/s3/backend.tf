terraform {
  backend "s3" {
    bucket         = "chat-ops-tfstate-s3"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "chat-ops-tf-lock"
  }
}