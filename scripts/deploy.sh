#!/bin/bash
# Deploy Vello to server: bash scripts/deploy.sh <server-ip> <path-to-pem>
# Example: bash scripts/deploy.sh 1.2.3.4 ~/.ssh/vello.pem
set -euo pipefail

SERVER_IP=${1:?Usage: deploy.sh <server-ip> <pem-file>}
PEM_FILE=${2:?Usage: deploy.sh <server-ip> <pem-file>}
REMOTE_DIR="/opt/vello"
SSH_OPTS="-i $PEM_FILE -o StrictHostKeyChecking=accept-new"

echo "Deploying to $SERVER_IP..."

rsync -avz --progress \
  --exclude='.git' \
  --exclude='**/__pycache__' \
  --exclude='*.pyc' \
  --exclude='vello.db' \
  --exclude='web/node_modules' \
  --exclude='web/dist' \
  --exclude='.env' \
  -e "ssh $SSH_OPTS" \
  . ubuntu@$SERVER_IP:$REMOTE_DIR/

echo "Files synced. Starting containers..."

ssh $SSH_OPTS ubuntu@$SERVER_IP << REMOTE
  cd $REMOTE_DIR
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from example — fill in before traffic arrives:"
    echo "  nano $REMOTE_DIR/.env"
    exit 1
  fi
  docker compose pull 2>/dev/null || true
  docker compose up -d --build
  docker compose ps
REMOTE

echo "Deploy complete. App at https://vello.flexflows.net"
