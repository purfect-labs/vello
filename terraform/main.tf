terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Networking ────────────────────────────────────────────────────────────────

resource "aws_vpc" "vello" {
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "${var.app_name}-vpc" }
}

resource "aws_internet_gateway" "vello" {
  vpc_id = aws_vpc.vello.id
  tags   = { Name = "${var.app_name}-igw" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.vello.id
  cidr_block              = "10.1.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.app_name}-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.vello.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.vello.id
  }
  tags = { Name = "${var.app_name}-public-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ── Security group ────────────────────────────────────────────────────────────

resource "aws_security_group" "vello" {
  name        = "${var.app_name}-sg"
  description = "Vello application security group"
  vpc_id      = aws_vpc.vello.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.app_name}-sg" }
}

# ── EC2 instance ──────────────────────────────────────────────────────────────

resource "aws_instance" "vello" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.vello.id]
  key_name               = var.key_pair_name

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  user_data = templatefile("${path.module}/userdata.sh", {
    app_name = var.app_name
  })

  tags = { Name = "${var.app_name}-server" }

  lifecycle {
    ignore_changes = [ami]
  }
}

resource "aws_eip" "vello" {
  instance = aws_instance.vello.id
  domain   = "vpc"
  tags     = { Name = "${var.app_name}-eip" }

  depends_on = [aws_internet_gateway.vello]
}

# ── DNS ───────────────────────────────────────────────────────────────────────

data "aws_route53_zone" "flexflows" {
  zone_id = "Z00443311DAYWFEPD4MH9"
}

resource "aws_route53_record" "vello" {
  zone_id = data.aws_route53_zone.flexflows.zone_id
  name    = "vello.flexflows.net"
  type    = "A"
  ttl     = 300
  records = [aws_eip.vello.public_ip]
}
