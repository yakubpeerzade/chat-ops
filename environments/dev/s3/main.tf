module "s3" {
  source = "../../../modules/s3"

  bucket_name   = var.bucket_name
  project_code  = var.project_code
  project_owner = var.project_owner
}