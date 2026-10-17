#!/usr/bin/env bash
# Install k3s (single node) + Helm on the Pi. Run after 00-prepare-pi.sh and the reboot.
set -euo pipefail

echo "== Checks"
uname -m                                  # expect aarch64
getconf PAGESIZE                          # expect 4096 (4K-page kernel)
grep -q cgroup_enable=memory /proc/cmdline && echo "memory cgroup: OK"

echo "== Install k3s (includes containerd, Traefik ingress, ServiceLB, local-path storage)"
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644

echo "== kubeconfig for your user"
mkdir -p ~/.kube
cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
grep -q KUBECONFIG ~/.bashrc || echo 'export KUBECONFIG=$HOME/.kube/config' >> ~/.bashrc
export KUBECONFIG=$HOME/.kube/config

echo "== Install Helm"
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

kubectl get nodes -o wide
echo "Done. Next: cp lab.env.example lab.env, edit it, then: bash install.sh"
echo "Tip: to use kubectl from your laptop, copy ~/.kube/config and replace 127.0.0.1 with the Pi IP."
