resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  tags = {
    Name                 = var.bucket_name
    project_code         = var.project_code
    project_owner        = var.project_owner
    resource_provisioned = "s3"
  }
}