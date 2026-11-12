#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu server. Run as root:
#   bash scripts/prod-server-setup.sh
# Installs Docker, turns on the firewall (SSH, 80, 443 only), enables automatic
# security updates, adds swap, and schedules a nightly backup.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Run as root (sudo bash scripts/prod-server-setup.sh)" >&2; exit 1; fi
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get -y upgrade
apt-get -y install ca-certificates curl git ufw unattended-upgrades cron

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF

if ! swapon --show | grep -q .; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

mkdir -p /opt/imhire-backups
chmod 700 /opt/imhire-backups

# Nightly backup at 20:30 UTC (02:00 India time).
echo "30 20 * * * root cd $REPO_ROOT && bash scripts/prod-backup.sh >> /var/log/imhire-backup.log 2>&1" > /etc/cron.d/imhire-backup
chmod 644 /etc/cron.d/imhire-backup

echo
echo "Server ready. Next: create .env.prod, then run: bash scripts/prod-deploy.sh"
