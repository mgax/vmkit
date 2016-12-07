#!/bin/sh
set -e

cd /target
mkdir 'etc/systemd/system/serial-getty@ttyS0.service.d'
cat > 'etc/systemd/system/serial-getty@ttyS0.service.d/override.conf' <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF

echo '/sbin/poweroff' > root/.bash_logout

cat > 'usr/local/sbin/run_and_poweroff' <<EOF
#!/bin/sh

# execute command
"$@"

# then poweroff
/sbin/poweroff
EOF
chmod +x 'usr/local/sbin/run_and_poweroff'
