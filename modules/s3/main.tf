# module "s3" {
#   source = "../../../modules/s3"

#   bucket_name         = var.bucket_name
#   project_code        = var.project_code
#   project_owner       = var.project_owner
#   request_id          = var.request_id
#   versioning_enabled  = var.versioning_enabled
#   block_public_access = var.block_public_access
# }

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
  force_destroy = true
  tags = {
    Name                 = var.bucket_name
    project_code         = var.project_code
    project_owner        = var.project_owner
    request_id           = var.request_id
    resource_provisioned = "s3"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  count                   = var.block_public_access ? 1 : 0
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = var.versioning_enabled ? "Enabled" : "Suspended"
  }
}