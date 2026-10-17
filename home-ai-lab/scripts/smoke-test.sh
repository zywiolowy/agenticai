#!/usr/bin/env bash
# End-to-end check of every component. Run on the Pi (or any machine on your LAN):
#   bash scripts/smoke-test.sh            # reads k8s/lab.env
set -u
cd "$(dirname "$0")/.."
[ -f k8s/lab.env ] && { set -a; source k8s/lab.env; set +a; }
PC_IP=${PC_IP:-192.168.1.10}
PI_IP=${PI_IP:-192.168.1.20}
VLLM_KEY=${VLLM_API_KEY:-change-me-vllm-key}
LITELLM_KEY=${LITELLM_MASTER_KEY:-sk-change-me-master}
LITELLM="http://litellm.${PI_IP}.nip.io"

check() { local name=$1; shift; if "$@" >/dev/null 2>&1; then echo "OK    $name"; else echo "FAIL  $name"; fi; }

echo "--- Windows PC"
check "vLLM health"               curl -sf "http://$PC_IP:8000/health"
check "vLLM models (API key)"     curl -sf -H "Authorization: Bearer $VLLM_KEY" "http://$PC_IP:8000/v1/models"
check "vLLM metrics"              curl -sf "http://$PC_IP:8000/metrics"
check "Langfuse"                  curl -sf "http://$PC_IP:3000/api/public/health"

echo "--- Pi (k3s)"
if command -v kubectl >/dev/null; then
  kubectl -n ai-lab get pods --no-headers 2>/dev/null | awk '{printf "      pod %-40s %s\n", $1, $3}'
fi
check "Qdrant"                    curl -sf "http://qdrant.${PI_IP}.nip.io/readyz"
check "LiteLLM liveness"          curl -sf "$LITELLM/health/liveliness"
check "Open WebUI"                curl -sf "http://webui.${PI_IP}.nip.io/health"
check "Prometheus"                curl -sf "http://prometheus.${PI_IP}.nip.io/-/ready"
check "Grafana"                   curl -sf "http://grafana.${PI_IP}.nip.io/api/health"

echo "--- In-cluster path: LiteLLM pod -> vllm Service -> Windows PC"
if command -v kubectl >/dev/null; then
  check "litellm pod reaches vLLM" kubectl -n ai-lab exec deploy/litellm -- \
    python3 -c "import urllib.request;urllib.request.urlopen('http://vllm:8000/health',timeout=5)"
fi

echo "--- Through the gateway"
echo -n "  chat  (Pi -> PC GPU): "
curl -s "$LITELLM/v1/chat/completions" \
  -H "Authorization: Bearer $LITELLM_KEY" -H "Content-Type: application/json" \
  -d '{"model":"local-chat","messages":[{"role":"user","content":"Say hello in 5 words."}],"max_tokens":20}' \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["choices"][0]["message"]["content"])' \
  || echo "FAIL"
echo -n "  embed (Pi CPU): "
curl -s "$LITELLM/v1/embeddings" \
  -H "Authorization: Bearer $LITELLM_KEY" -H "Content-Type: application/json" \
  -d '{"model":"embed","input":"hello"}' \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print("dims =", len(d["data"][0]["embedding"]))' \
  || echo "FAIL"
