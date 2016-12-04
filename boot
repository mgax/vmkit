#!/bin/bash
set -e

args=(
  qemu-system-x86_64
  -enable-kvm
  -smp 1
  -m 256
  -cdrom debian-8.6-serial-install.iso
  -boot d
  -nographic
)

exec "${args[@]}"
