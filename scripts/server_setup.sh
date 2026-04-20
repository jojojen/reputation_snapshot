#!/bin/bash
# Run ONCE on a fresh Hetzner CX11 (Ubuntu 22.04)
# Usage: ssh root@<vps-ip> "bash -s" < scripts/server_setup.sh
set -e

echo "=== [1/5] System update ==="
apt-get update && apt-get upgrade -y

echo "=== [2/5] Install Docker ==="
curl -fsSL https://get.docker.com | sh
apt-get install -y docker-compose-plugin

echo "=== [3/5] Firewall — allow only SSH + HTTP ==="
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw --force enable
echo "Firewall status:"
ufw status

echo "=== [4/5] Clone repo ==="
# Replace with your actual git repo URL
GIT_REPO="${GIT_REPO:-https://github.com/YOUR_USERNAME/reputation_snapshot.git}"
git clone "$GIT_REPO" /app
cd /app

echo "=== [5/5] Configure .env ==="
cp .env.production .env
echo ""
echo "========================================"
echo " NEXT STEPS:"
echo "  1. Edit /app/.env — set ADMIN_TOKEN and R2 credentials"
echo "  2. cd /app && docker compose up -d --build"
echo "  3. Access: http://$(curl -s ifconfig.me)"
echo "========================================"
