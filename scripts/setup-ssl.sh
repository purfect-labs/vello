#!/bin/bash
# Usage: bash scripts/setup-ssl.sh vello.flexflows.net your@email.com
set -euo pipefail

DOMAIN=${1:?Usage: setup-ssl.sh <domain> <email>}
EMAIL=${2:?Usage: setup-ssl.sh <domain> <email>}
APP_DIR="/opt/vello"

echo "Setting up SSL for $DOMAIN..."

# Ensure certbot webroot dir exists
mkdir -p /var/www/certbot

# Get certificate (HTTP-01 challenge via webroot — requires port 80 to be up first)
certbot certonly --webroot \
  -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos \
  --non-interactive

# Restart frontend container to pick up the cert
cd "$APP_DIR"
docker compose restart frontend

# Auto-renewal cron
echo "0 3 * * * root certbot renew --quiet && docker compose -f $APP_DIR/docker-compose.yml restart frontend" \
  > /etc/cron.d/certbot-renewal

echo "SSL configured for https://$DOMAIN"
