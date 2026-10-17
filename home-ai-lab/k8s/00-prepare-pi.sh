#!/usr/bin/env bash
# One-time Raspberry Pi 5 preparation for k3s. Run on the Pi (Raspberry Pi OS Lite 64-bit).
#   bash 00-prepare-pi.sh      -> reboots at the end
set -euo pipefail

CMDLINE=/boot/firmware/cmdline.txt
CONFIG=/boot/firmware/config.txt

echo "== Packages"
sudo apt-get update
sudo apt-get install -y curl git jq gettext-base python3-venv

echo "== Enable memory cgroups (required by Kubernetes)"
if ! grep -q "cgroup_enable=memory" "$CMDLINE"; then
  sudo sed -i '1 s/$/ cgroup_memory=1 cgroup_enable=memory/' "$CMDLINE"
fi

echo "== Use the 4K-page kernel (avoids Qdrant/jemalloc crashes with the Pi 5 16K-page kernel)"
if ! grep -q "^kernel=kernel8.img" "$CONFIG"; then
  echo "kernel=kernel8.img" | sudo tee -a "$CONFIG" >/dev/null
fi

echo "== Disable swap (Kubernetes prefers no swap)"
if systemctl list-unit-files | grep -q dphys-swapfile; then
  sudo dphys-swapfile swapoff || true
  sudo systemctl disable dphys-swapfile || true
fi

echo "Done. Rebooting in 5 s... After reboot run: bash 01-install-k3s.sh"
sleep 5
sudo reboot
