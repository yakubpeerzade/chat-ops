variable "ami_id" {
  type        = string
  description = "AMI ID for EC2 instance"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type"
}

variable "instance_name" {
  type        = string
  description = "Name of EC2 instance"
}

variable "project_code" {
  type        = string
  description = "Project code"
}

variable "project_owner" {
  type        = string
  description = "Project owner"
}