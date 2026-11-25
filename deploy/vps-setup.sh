#!/usr/bin/env bash
# One-time hardening of a fresh Ubuntu 24.04 VPS. Read it before running.
# Run as root on the server, AFTER you can log in with an SSH key:
#
#   sudo bash deploy/vps-setup.sh deploy
#
# It creates the given sudo user (default "deploy") with root's SSH keys,
# turns off password and root SSH login, opens only ports 22/80/443, enables
# fail2ban and automatic security updates, and installs Docker Engine.
# Keep your current SSH session open until you have tested a new login.
set -euo pipefail

USER_NAME="${1:-deploy}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi
if [[ ! -s /root/.ssh/authorized_keys ]]; then
  echo "/root/.ssh/authorized_keys is empty. Add your SSH key first, or you will be locked out." >&2
  exit 1
fi

echo "== Packages and automatic security updates"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
DEBIAN_FRONTEND=noninteractive apt-get -y install ufw fail2ban unattended-upgrades ca-certificates curl git openssl
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== User ${USER_NAME}"
if ! id "${USER_NAME}" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "${USER_NAME}"
fi
usermod -aG sudo "${USER_NAME}"
install -d -m 700 -o "${USER_NAME}" -g "${USER_NAME}" "/home/${USER_NAME}/.ssh"
install -m 600 -o "${USER_NAME}" -g "${USER_NAME}" /root/.ssh/authorized_keys "/home/${USER_NAME}/.ssh/authorized_keys"

echo "== SSH: keys only, no root login"
cat > /etc/ssh/sshd_config.d/10-lucid.conf <<'SSHD'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
SSHD
sshd -t
systemctl reload ssh

echo "== Firewall: 22, 80, 443 only"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "== fail2ban (SSH)"
systemctl enable --now fail2ban

echo "== Docker Engine (official repository)"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker "${USER_NAME}"

echo "Done. In a NEW terminal, check: ssh ${USER_NAME}@<server>  (then close the root session)."
