#!/bin/bash
# Deploy latest code to VPS
# Usage: ./scripts/deploy.sh
set -e

VPS_USER="${VPS_USER:-root}"
VPS_IP="${VPS_IP:?Set VPS_IP environment variable}"

echo "[deploy] Pushing to $VPS_USER@$VPS_IP ..."
ssh "$VPS_USER@$VPS_IP" "cd /app && git pull && docker compose up -d --build"
echo "[deploy] Done. App running at http://$VPS_IP"
