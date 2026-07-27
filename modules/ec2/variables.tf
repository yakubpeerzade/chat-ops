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

variable "root_volume_size" {
  type        = number
  description = "Root volume size in GB"
  default     = 20
}