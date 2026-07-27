module "ec2" {
  source = "../../../modules/ec2"

  request_id         = var.request_id
  os_name            = var.os_name
  instance_type      = var.instance_type
  subnet_id          = var.subnet_id
  security_group_ids = var.security_group_ids
  instance_name      = var.instance_name
  project_code       = var.project_code
  project_owner      = var.project_owner
}