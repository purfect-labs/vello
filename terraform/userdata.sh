#!/bin/bash
set -euo pipefail
exec > /var/log/vello-init.log 2>&1

APP_NAME="${app_name}"

# System update
apt-get update -y
apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
systemctl enable docker
systemctl start docker

# Install Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Install utilities
apt-get install -y git curl unzip certbot python3-certbot-nginx ufw

# Firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Create app directory
mkdir -p /opt/$APP_NAME
chown ubuntu:ubuntu /opt/$APP_NAME

echo "Bootstrap complete — $(date)"
