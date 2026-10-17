#!/usr/bin/env bash
# Remove the lab from the cluster. Add --purge to also delete all data volumes.
set -euo pipefail
export KUBECONFIG=${KUBECONFIG:-$HOME/.kube/config}

helm uninstall monitoring -n monitoring || true
helm uninstall qdrant -n ai-lab || true

if [ "${1:-}" = "--purge" ]; then
  kubectl delete namespace ai-lab monitoring --ignore-not-found
  echo "Namespaces and all data volumes deleted."
else
  kubectl -n ai-lab delete deploy,statefulset,job,svc,ingress,configmap --all --ignore-not-found
  echo "Workloads removed. Data volumes (PVCs) and the secret were kept. Use --purge to delete everything."
fi
