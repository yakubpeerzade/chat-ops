locals {
  ami_ssm_paths = {
    ubuntu         = "/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id"
    amazonlinux23  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    windows        = "/aws/service/ami-windows-latest/Windows_Server-2022-English-Full-Base"
  }
}

data "aws_ssm_parameter" "ami" {
  name = local.ami_ssm_paths[var.os_name]
}