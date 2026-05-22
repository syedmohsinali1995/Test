#!/bin/bash
# One-command deployment script for DigitalOcean Ubuntu server
# Run this on a fresh Ubuntu 22.04 droplet:
#   bash deploy_digitalocean.sh

set -e
echo "================================================"
echo "  AI Real Estate Agent - DigitalOcean Deploy"
echo "================================================"

# 1. Update system
apt-get update -y && apt-get upgrade -y

# 2. Install Docker
echo "[1/5] Installing Docker..."
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# 3. Install Docker Compose
echo "[2/5] Installing Docker Compose..."
apt-get install -y docker-compose-plugin

# 4. Clone / copy project
echo "[3/5] Setting up project..."
mkdir -p /opt/realestateai
cp -r . /opt/realestateai/
cd /opt/realestateai

# 5. Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "================================================"
    echo "  IMPORTANT: Edit /opt/realestateai/.env"
    echo "  Set: PUBLIC_URL, SUPER_ADMIN_EMAIL, etc."
    echo "================================================"
    nano .env
fi

# 6. Start with Docker Compose
echo "[4/5] Starting application..."
docker compose up -d --build

# 7. Install Nginx + SSL
echo "[5/5] Installing Nginx..."
apt-get install -y nginx certbot python3-certbot-nginx

# Write Nginx config
read -p "Enter your domain name (e.g. ai.yourcompany.com): " DOMAIN

cat > /etc/nginx/sites-available/realestateai << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

ln -sf /etc/nginx/sites-available/realestateai /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# SSL certificate
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

echo ""
echo "================================================"
echo "  DEPLOYMENT COMPLETE!"
echo "  Your app is live at: https://$DOMAIN"
echo "================================================"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f          # View logs"
echo "  docker compose restart          # Restart"
echo "  docker compose down             # Stop"
