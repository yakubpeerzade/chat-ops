variable "os_name" {
  type = string
  validation {
    condition     = contains(["ubuntu", "windows", "amazonlinux23"], var.os_name)
    error_message = "os_name must be ubuntu, windows or amazonlinux23."
  }
}

variable "instance_type" {
  type = string
  validation {
    condition = contains([
      "t2.micro", "t2.small", "t2.medium",
      "t3.micro", "t3.small", "t3.medium", "t3.large",
      "t3a.micro", "t3a.small", "t3a.medium",
      "m5.large", "m5.xlarge",
    ], var.instance_type)
    error_message = "instance_type is not on the approved list."
  }
}

variable "subnet_id"          { type = string }
variable "security_group_ids" { type = list(string)}
variable "key_name"{ 
  type = string
  default = null 
}
variable "root_volume_size"{ 
  type = number
  default = 20 
}
variable "request_id" { type = string }