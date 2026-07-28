module "s3" {
  source = "../../../modules/s3"

  bucket_name         = var.bucket_name
  project_code        = var.project_code
  project_owner       = var.project_owner
  request_id          = var.request_id
  versioning_enabled  = var.versioning_enabled
  block_public_access = var.block_public_access
}