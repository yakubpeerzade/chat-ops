variable "request_id" {
  type    = string
  default = null
}

variable "os_name" {
  type    = string
  default = "ubuntu"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "root_volume_size" {
  type    = number
  default = 20
}

variable "key_name" {
  type    = string
  default = null
}

variable "instance_name" {
  type    = string
  default = null
}

variable "project_code" {
  type    = string
  default = null
}

variable "project_owner" {
  type    = string
  default = null
}

variable "subnet_id" {
  type    = string
  default = null
}

variable "security_group_ids" {
  type    = list(string)
  default = []
}