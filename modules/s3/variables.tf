variable "bucket_name" {
  type = string
}

variable "project_code" {
  type = string
}

variable "project_owner" {
  type = string
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