resource "aws_instance" "this" {
  ami           = var.ami_id
  instance_type = var.instance_type

  tags = {
    Name                 = var.instance_name
    project_code         = var.project_code
    project_owner        = var.project_owner
    resource_provisioned = "ec2"
  }
}