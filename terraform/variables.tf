variable "app_name" {
  description = "Application name used for resource naming"
  default     = "vello"
}

variable "aws_region" {
  description = "AWS region to deploy into"
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  default     = "t3.small"
}

variable "ami_id" {
  description = "Ubuntu 24.04 LTS AMI (us-east-1)"
  default     = "ami-0c7217cdde317cfec"
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access"
  type        = string
}

variable "ssh_cidr" {
  description = "CIDR allowed for SSH — restrict to your IP (e.g. 1.2.3.4/32)"
  default     = "0.0.0.0/0"
}
