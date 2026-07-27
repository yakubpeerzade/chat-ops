# Variables passed via .tfvars
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

variable "root_volume_size" {
  type        = number
  description = "Root disk volume size in GB"
  default     = 20
}

variable "instance_name" {
  type        = string
  default     = null
}

variable "project_code" {
  type        = string
  default     = null
}

variable "project_owner" {
  type        = string
  default     = null
}

# Optional network variables (defaulted to null so execution doesn't block)
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