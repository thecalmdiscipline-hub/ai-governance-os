#!/bin/bash
# Read-only server-hardening check (Batch "Serverhardening", 2026-10-13). Prints the same
# values the hand-off's Fase 0 / productiecontrole read, so Cowork or Dennis can repeat this
# check later without re-deriving it. Never prints an IP list or a secret — only counts and
# the effective sshd settings (which contain no secrets themselves).
set -euo pipefail

echo "=== uname -r ==="
uname -r

echo "=== reboot-required ==="
if [ -f /var/run/reboot-required ]; then
  echo "PENDING"
  cat /var/run/reboot-required.pkgs 2>/dev/null || true
else
  echo "none"
fi

echo "=== ufw status ==="
ufw status verbose | head -8

echo "=== fail2ban ==="
if command -v fail2ban-client >/dev/null 2>&1; then
  systemctl is-active fail2ban
  fail2ban-client status sshd | grep -E "Currently failed|Total failed|Currently banned|Total banned"
  fail2ban-client status recidive | grep -E "Currently failed|Total failed|Currently banned|Total banned"
else
  echo "not installed"
fi

echo "=== sshd effective settings (no secrets) ==="
sshd -T 2>/dev/null | grep -E \
  "passwordauthentication|permitrootlogin|maxauthtries|maxstartups|logingracetime|pubkeyauthentication|kbdinteractiveauthentication|permitemptypasswords|x11forwarding"

echo "=== disk / memory ==="
df -h / | tail -1
free -m | head -2

echo "=== services ==="
systemctl is-active valqeron nginx postgresql redis-server certbot.timer
