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

variable "request_id" {
  type        = string
  description = "Unique ticket request ID"
  default     = null
}

variable "os_name" {
  type        = string
  description = "Operating system (ubuntu, windows, amazonlinux23)"
  default     = "ubuntu"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance size"
  default     = "t3.micro"
}

variable "subnet_id" {
  type        = string
  description = "Target Subnet ID"
  default     = null
}

variable "security_group_ids" {
  type        = list(string)
  description = "List of Security Group IDs"
  default     = []
}

# Added missing variable declarations referenced by main.tf
variable "instance_name" {
  type        = string
  description = "Name tag for the EC2 instance"
  default     = null
}

variable "project_code" {
  type        = string
  description = "Project identifier tag"
  default     = null
}

variable "project_owner" {
  type        = string
  description = "Project requester/owner tag"
  default     = null
}