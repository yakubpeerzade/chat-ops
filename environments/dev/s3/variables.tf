variable "bucket_name" {
  type    = string
  default = "dummy-bucket"
}

variable "project_code" {
  type    = string
  default = "jade"
}

variable "project_owner" {
  type    = string
  default = "unknown"
}

variable "request_id" {
  type    = string
  default = "unknown"
}

variable "versioning_enabled" {
  type    = bool
  default = true
}

variable "block_public_access" {
  type    = bool
  default = true
}