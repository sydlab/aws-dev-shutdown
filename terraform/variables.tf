variable "aws_region" {
  type        = string
  description = "Region where EC2 dev instances live"
  default     = "us-east-1"
}

variable "github_org" {
  type        = string
  description = "GitHub org or user (e.g. sydlab)"
  default     = "sydlab"
}

variable "github_repo" {
  type        = string
  description = "Repository name only (e.g. aws-dev-shutdown)"
  default     = "aws-dev-shutdown"
}

variable "role_name" {
  type        = string
  description = "IAM role name for GitHub Actions"
  default     = "github-actions-aws-dev-shutdown"
}

variable "target_tag_key" {
  type    = string
  default = "AutoShutdown"
}

variable "target_tag_value" {
  type    = string
  default = "true"
}
