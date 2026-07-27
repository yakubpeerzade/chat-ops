resource "aws_instance" "this" {
  ami                    = nonsensitive(data.aws_ssm_parameter.ami.value)
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.security_group_ids
  key_name               = var.key_name

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"   # IMDSv2 only
    http_put_response_hop_limit = 1
  }

  root_block_device {
    encrypted             = true
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    delete_on_termination = true
  }

  tags = {
    Name                 = var.instance_name
    project_code         = var.project_code
    project_owner        = var.project_owner
    request_id           = var.request_id
    resource_provisioned = "ec2"
  }

  lifecycle {
    # AMI drift would otherwise force a replacement on every apply once the
    # SSM parameter advances to a newer image.
    ignore_changes = [ami]
  }
}