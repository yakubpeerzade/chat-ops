# toggles
variable "create_s3" {
  type    = bool
  default = false
}

variable "create_ec2" {
  type    = bool
  default = false
}

# S3
variable "bucket_name" {
  type    = string
  default = null
}

# EC2
variable "ami_id" {
  type    = string
  default = null
}

variable "instance_type" {
  type    = string
  default = null
}

variable "instance_name" {
  type    = string
  default = null
}

# common tags
variable "project_code" {
  type = string
}

variable "project_owner" {
  type = string
}

# backend control
variable "request_id" {
  type = string
}