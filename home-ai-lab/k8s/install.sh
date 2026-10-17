#!/usr/bin/env bash
# Deploy (or update) the whole Pi side of the lab. Safe to re-run after any change.
#   cp lab.env.example lab.env && nano lab.env
#   bash install.sh
set -euo pipefail
cd "$(dirname "$0")"
export KUBECONFIG=${KUBECONFIG:-$HOME/.kube/config}

[ -f lab.env ] || { echo "lab.env missing: cp lab.env.example lab.env and edit it"; exit 1; }
set -a; source lab.env; set +a

NS=ai-lab
VARS='${PC_IP} ${PI_IP} ${GRAFANA_PASSWORD} ${LITELLM_CONFIG_HASH}'   # only these get substituted
export LITELLM_CONFIG_HASH=$(sha256sum manifests/31-litellm.yaml lab.env | sha256sum | cut -c1-16)

echo "== Namespace"
kubectl apply -f manifests/00-namespace.yaml

echo "== Secret (from lab.env – never commit lab.env to Git)"
kubectl -n $NS create secret generic lab-secrets \
  --from-literal=VLLM_API_KEY="$VLLM_API_KEY" \
  --from-literal=LITELLM_MASTER_KEY="$LITELLM_MASTER_KEY" \
  --from-literal=LITELLM_DB_PASSWORD="$LITELLM_DB_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql://litellm:${LITELLM_DB_PASSWORD}@litellm-db:5432/litellm" \
  --from-literal=LANGFUSE_PUBLIC_KEY="$LANGFUSE_PUBLIC_KEY" \
  --from-literal=LANGFUSE_SECRET_KEY="$LANGFUSE_SECRET_KEY" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
  --from-literal=WEBUI_SECRET_KEY="$WEBUI_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "== Helm repos"
helm repo add qdrant https://qdrant.github.io/qdrant-helm >/dev/null 2>&1 || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null

echo "== Qdrant (Helm)"
helm upgrade --install qdrant qdrant/qdrant -n $NS -f helm/qdrant-values.yaml

echo "== Manifests: external PC services, Ollama, LiteLLM + Postgres, Open WebUI, Ingress"
for f in manifests/1*.yaml manifests/2*.yaml manifests/3*.yaml manifests/4*.yaml manifests/5*.yaml; do
  echo "   $f"
  envsubst "$VARS" < "$f" | kubectl apply -f -
done

echo "== Monitoring: Prometheus + Grafana (Helm)"
envsubst "$VARS" < helm/monitoring-values.yaml | \
  helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
    -n monitoring --create-namespace -f -

echo "== Waiting for pods (first run pulls images – can take 10+ minutes on a Pi)"
for d in ollama litellm open-webui; do
  kubectl -n $NS rollout status deploy/$d --timeout=20m || true
done
kubectl -n $NS rollout status statefulset/litellm-db --timeout=10m || true
kubectl -n $NS rollout status statefulset/qdrant --timeout=10m || true

cat <<EOF

Done. Open:
  Chat (Open WebUI)   http://webui.${PI_IP}.nip.io
  LiteLLM admin UI    http://litellm.${PI_IP}.nip.io/ui     (log in with LITELLM_MASTER_KEY)
  Qdrant dashboard    http://qdrant.${PI_IP}.nip.io/dashboard
  Grafana             http://grafana.${PI_IP}.nip.io        (admin / GRAFANA_PASSWORD)
  Prometheus          http://prometheus.${PI_IP}.nip.io
  Langfuse (PC)       http://${PC_IP}:3000

Check everything:  bash ../scripts/smoke-test.sh
EOF
