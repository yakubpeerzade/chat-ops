module "ec2" {
  source = "../../../modules/ec2"

  ami_id         = var.ami_id
  instance_type  = var.instance_type
  instance_name  = var.instance_name
  project_code   = var.project_code
  project_owner  = var.project_owner
}