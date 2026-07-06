module "s3" {
  source = "../../modules/s3"
  count  = var.create_s3 ? 1 : 0

  bucket_name   = var.bucket_name
  project_code  = var.project_code
  project_owner = var.project_owner
}

module "ec2" {
  source = "../../modules/ec2"
  count  = var.create_ec2 ? 1 : 0

  ami_id         = var.ami_id
  instance_type  = var.instance_type
  instance_name  = var.instance_name
  project_code   = var.project_code
  project_owner  = var.project_owner
}