#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Vir — Post-install script (shared by DEB and RPM)
# ═══════════════════════════════════════════════════════════════════
set -e

# Create system user
if ! getent group vir >/dev/null 2>&1; then
    groupadd -r vir
fi
if ! getent passwd vir >/dev/null 2>&1; then
    useradd -r -g vir -d /var/lib/vir -s /usr/sbin/nologin \
        -c "Vir Language Runtime" vir
fi

# Create directories
install -d -m 0750 -o vir -g vir /var/lib/vir
install -d -m 0750 -o vir -g vir /var/log/vir
install -d -m 0750 -o vir -g vir /var/cache/vir

# Update shared library cache
ldconfig

# Reload systemd
if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    systemctl enable vir.service 2>/dev/null || true
fi

echo "Vir Language installed successfully."
echo "  Start server: systemctl start vir"
echo "  Run REPL:     vir"
echo "  Config:       /etc/vir/vir.conf"
