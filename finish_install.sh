#!/bin/sh
set -e

cd /target/etc/systemd/system
mkdir 'serial-getty@ttyS0.service.d'
cat > 'serial-getty@ttyS0.service.d/override.conf' <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF

echo '/sbin/poweroff' > /root/.bash_logout
