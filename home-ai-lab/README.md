# Home AI Lab – Windows PC (GPU) + Raspberry Pi 5 on k3s

Learn hands-on how **RAG** and **vLLM** work, on a small copy of a production LLM platform.

- **Windows PC (RTX 4070 Super):** vLLM and Langfuse in Docker Desktop. The GPU stays outside Kubernetes.
- **Raspberry Pi 5 16 GB:** single-node **k3s** cluster with Qdrant, Ollama embeddings, LiteLLM gateway,
  Open WebUI, Prometheus and Grafana.
- Pods reach the PC through Kubernetes Services that point outside the cluster, so inside the cluster
  vLLM is just `http://vllm:8000`.

## 1. Architecture

```
                         Laptop / browser
                                │  http://*.PI_IP.nip.io  (port 80)
┌───────────────────────────────▼───────────────────────────┐      ┌──────────────────────────────────┐
│ Raspberry Pi 5 – k3s (single node)                        │      │ Windows PC – Docker Desktop      │
│                                                           │      │ (WSL2 backend, RTX 4070 Super)   │
│  Traefik Ingress (built into k3s)                         │      │                                  │
│   webui.* → Open WebUI ─┐                                 │      │  vLLM          :8000             │
│   litellm.* → LiteLLM ◄─┘ ──► Service "vllm" ─────────────┼─────►│   Qwen2.5-7B-AWQ, /v1, /metrics  │
│                │            (EndpointSlice → PC_IP:8000)  │      │                                  │
│                ├──► Ollama (CPU) – embeddings             │      │  Langfuse      :3000             │
│                └──► Postgres (keys, budgets)              │      │   + Postgres, ClickHouse,        │
│   qdrant.* → Qdrant (Helm) – vector DB                    │      │     Redis, MinIO                 │
│   grafana.* / prometheus.* → kube-prometheus-stack ───────┼─────►│  (scrapes vLLM /metrics)         │
│                             Service "langfuse" ───────────┼─────►│                                  │
└───────────────────────────────────────────────────────────┘      └──────────────────────────────────┘

RAG scripts (rag/*.py) run on your laptop, PC or Pi:
 question → LiteLLM "embed" (Pi) → Qdrant search (Pi) → LiteLLM "local-chat" → vLLM (PC GPU)
 every step → Langfuse trace (PC)
```

## 2. What's in the kit

```
pc/                     Windows PC
  docker-compose.yml    vLLM (+ optional Ollama-GPU profile)
  .env.example
  windows-firewall.ps1  opens ports 8000 and 3000 on the Private network
k8s/                    Raspberry Pi (k3s)
  00-prepare-pi.sh      cgroups, 4K-page kernel, no swap  (reboots)
  01-install-k3s.sh     k3s + Helm
  lab.env.example       IPs, keys, passwords
  install.sh            deploys / updates everything (safe to re-run)
  uninstall.sh          removes it (--purge also deletes data)
  manifests/            namespace, external PC Services, Ollama, LiteLLM + Postgres, Open WebUI, Ingress
  helm/                 values for Qdrant and kube-prometheus-stack
rag/                    RAG app: ingest.py, ask.py, eval.py, golden.jsonl, sample docs
scripts/                bench.py (vLLM load test), smoke-test.sh
```

## 3. Before you start
- Give both machines a fixed IP (DHCP reservation in your router). The examples use PC `192.168.1.10`
  and Pi `192.168.1.20`.
- Pi: Raspberry Pi OS Lite 64-bit (Debian-based). Boot from an NVMe SSD if you can; SD cards are slow
  for Postgres, Qdrant and Prometheus.
- The `nip.io` hostnames need internet DNS. If your router blocks that, see Troubleshooting.

## 4. Windows PC setup

1. Update the NVIDIA Windows driver. Don't install any NVIDIA driver inside WSL.
2. Install WSL2 (`wsl --install` in an admin PowerShell, then reboot) and **Docker Desktop**
   (Settings → General → "Use the WSL 2 based engine").
3. Test GPU access from Docker (PowerShell):
   ```powershell
   docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
   ```
   It must show the RTX 4070 Super.
4. Open the firewall (PowerShell as Administrator): `.\pc\windows-firewall.ps1`
5. Start vLLM:
   ```powershell
   cd pc
   copy .env.example .env      # set VLLM_API_KEY to a long random string
   docker compose up -d
   docker logs -f vllm         # first start downloads ~5 GB; wait for "Application startup complete"
   ```
6. Start Langfuse (official compose):
   ```powershell
   git clone https://github.com/langfuse/langfuse.git
   cd langfuse
   # Edit docker-compose.yml: change every value marked "# CHANGEME".
   # Set NEXTAUTH_URL=http://192.168.1.10:3000 (your PC IP) so the UI works from the LAN.
   docker compose up -d
   ```
   Open `http://PC_IP:3000`, create an account, organisation and project, then create API keys
   (Settings → API Keys).

Keep Docker Desktop running ("Start Docker Desktop when you sign in") so vLLM is up whenever the PC is on.

## 5. Raspberry Pi setup (k3s)

```bash
git clone <your copy of this kit> home-ai-lab   # or scp the folder
cd home-ai-lab/k8s
bash 00-prepare-pi.sh        # reboots
# after reboot:
cd home-ai-lab/k8s
bash 01-install-k3s.sh
cp lab.env.example lab.env && nano lab.env    # IPs, VLLM_API_KEY (same as PC), keys, Langfuse keys
bash install.sh
```

The first `install.sh` run pulls about 5 GB of images and can take 10–20 minutes on a Pi.

| UI | URL |
|---|---|
| Chat (Open WebUI) | http://webui.PI_IP.nip.io |
| LiteLLM admin (keys, budgets, spend) | http://litellm.PI_IP.nip.io/ui (log in with the master key) |
| Qdrant dashboard | http://qdrant.PI_IP.nip.io/dashboard |
| Grafana | http://grafana.PI_IP.nip.io (admin / GRAFANA_PASSWORD) |
| Prometheus | http://prometheus.PI_IP.nip.io |
| Langfuse | http://PC_IP:3000 |

Check everything: `bash scripts/smoke-test.sh`

### Kubernetes things you practise here
| Concept | Where |
|---|---|
| Service without selector + EndpointSlice (external backend) | `manifests/10-external-pc.yaml` |
| Deployment, Service, PVC, `Recreate` strategy for RWO volumes | Ollama, Open WebUI |
| StatefulSet + volumeClaimTemplates + headless Service | Postgres |
| ConfigMap mounted as a file, config-hash annotation to trigger restarts | LiteLLM |
| Secret from env file, `envFrom` / `secretKeyRef` | `install.sh`, LiteLLM, Open WebUI |
| startup / readiness / liveness probes, requests and limits | every workload |
| One-off Job with retries | `ollama-pull` |
| Ingress with Traefik | `manifests/50-ingress.yaml` |
| Helm charts with your own values | Qdrant, kube-prometheus-stack |

Useful commands:
```bash
kubectl -n ai-lab get pods,svc,pvc,ingress
kubectl -n ai-lab logs deploy/litellm -f
kubectl -n ai-lab describe pod <pod>
kubectl -n ai-lab get endpointslices            # see the PC IP behind "vllm" and "langfuse"
kubectl -n ai-lab exec -it deploy/litellm -- sh
kubectl top pods -A                             # metrics-server is included in k3s
```

## 6. Lab A – RAG, step by step

Run the scripts on your laptop or PC (Python 3.10+):
```bash
cd rag
python -m venv .venv
.venv\Scripts\activate          # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # set IPs, LiteLLM key, Langfuse keys
python ingest.py --recreate
python ask.py "How do I roll back a bad deployment?"
python ask.py "What is the capital of France?"     # should answer "I don't know..."
```

What to look at and try:
1. **Embeddings and vectors.** In the Qdrant dashboard, open the `docs` collection. Each point is a
   768-number vector plus a payload (text, source, heading, team).
2. **Chunking.** Change `MAX_CHARS` in `ingest.py` (500 vs 2000), re-ingest with `--recreate`, and compare
   answers and retrieved sources.
3. **Top-k.** `python ask.py "..." --k 1` vs `--k 8`. Fewer chunks miss context; more chunks add noise and tokens.
4. **Metadata filtering (access control).** Ingest a second set with `--team qa`, then query with
   `--team qa` and `--team engineering`. Filtering happens inside the search, before the model sees anything.
5. **Grounding.** The system prompt forces "answer only from context, cite sources, else say I don't know".
   Remove that rule and watch the model start inventing answers.
6. **Your own data.** Put your runbooks or notes (`.md`/`.txt`) in `docs/` and ingest them.
7. **Tracing.** In Langfuse, open a trace: `rag-answer` → `retrieve` → embedding call → chat generation,
   with the exact prompt, tokens and latency.
8. **Evaluation.**
   ```bash
   python eval.py              # hit@k (retrieval) + keyword match
   python eval.py --judge      # + LLM-as-a-judge faithfulness
   ```
   Make a bad change on purpose (`TOP_K=1`, tiny chunks) and watch `eval.py` fail with exit code 1.
   That is a CI quality gate.

Next RAG upgrades to build yourself:
- **Hybrid search:** add a sparse/BM25 vector to the Qdrant collection and fuse the results (RRF). It helps
  with exact terms like error codes.
- **Reranking:** retrieve 20, rerank with a cross-encoder, keep 5.
- **Incremental sync:** a Kubernetes CronJob that re-ingests changed files.

## 7. Lab B – How vLLM works

### Concepts to see with your own eyes
| Concept | What it means | How to see it |
|---|---|---|
| Model weights in VRAM | 7B in 4-bit AWQ ≈ 5 GB | `nvidia-smi` in PowerShell after start |
| KV-cache | The rest of the allowed VRAM is split into blocks that store attention keys/values per token | vLLM start-up log: "GPU KV cache size: N tokens" and "Maximum concurrency" |
| PagedAttention | KV-cache is allocated in small blocks on demand, like virtual memory pages, so little is wasted | Concurrency stays high without OOM |
| Continuous batching | New requests join the running batch at every step instead of waiting | `bench.py`: total tok/s rises with concurrency |
| Prefix caching | Requests that share a prompt start (e.g. same system prompt) reuse cached KV blocks | Prometheus prefix-cache hit metrics; faster TTFT for repeated prompts |
| Quantization | AWQ 4-bit weights: less VRAM, small quality loss | Compare an AWQ model vs a smaller full-precision one |

### Experiments
1. **Benchmark** (from any machine with Python; `pip install openai`):
   ```bash
   python scripts/bench.py --url http://PC_IP:8000/v1 --key <VLLM_API_KEY> --model qwen2.5-7b
   ```
   Watch TTFT and total tok/s at 1, 4, 8 and 16 parallel requests.
2. **Memory knobs.** In `pc/.env` change `MAX_MODEL_LEN` (4096 / 8192 / 16384) and `GPU_UTIL`
   (0.70 / 0.80 / 0.90), then `docker compose up -d` and read the KV-cache line in `docker logs vllm`.
   Longer context = fewer concurrent requests.
3. **Live metrics.** In Prometheus or Grafana, query while the benchmark runs:
   - `vllm:num_requests_running` and `vllm:num_requests_waiting` – batching and queueing
   - `vllm:gpu_cache_usage_perc` (newer versions: `vllm:kv_cache_usage_perc`) – KV-cache pressure
   - `rate(vllm:generation_tokens_total[1m])` – throughput
   - `histogram_quantile(0.95, rate(vllm:time_to_first_token_seconds_bucket[5m]))` – p95 TTFT

   The exact metric names change between vLLM versions. Check `curl http://PC_IP:8000/metrics`.
   Import the official vLLM Grafana dashboard JSON from the vLLM repository (observability examples).
4. **Prefix caching.** Run `ask.py` several times. The long system prompt is cached after the first call,
   so time-to-first-token drops. Then remove `--enable-prefix-caching` and compare.
5. **vLLM vs Ollama.** `docker compose stop vllm`, then `docker compose --profile ollama up -d`, pull a
   similar 7B model in Ollama, and run `bench.py` against `http://PC_IP:11434/v1`. Ollama is great for one
   user; vLLM wins under concurrency.
6. **Tool calling.** vLLM already runs with `--enable-auto-tool-choice --tool-call-parser hermes`. Send a
   chat request with a `tools` array through LiteLLM. That's the basis for agents.
7. **Different models.** Try `Qwen/Qwen2.5-3B-Instruct` (full precision, faster) or another AWQ model.
   Update `SERVED_NAME` in `pc/.env` and the `hosted_vllm/<name>` line in `k8s/manifests/31-litellm.yaml`,
   then re-run `install.sh`.

## 8. Lab C – the gateway (LiteLLM)
- In the LiteLLM UI, create a virtual key for a pretend team "qa" with a $1 budget and a rate limit.
  Use it in `rag/.env`.
- Uncomment a `cloud-chat` model and the `fallbacks` line in `31-litellm.yaml`, re-run `install.sh`, stop
  vLLM on the PC, and send a chat. The gateway falls back to the cloud model.
- Enable `success_callback: ["langfuse"]` to see gateway-level traces for all traffic, including Open WebUI.

## 9. Later (optional)
- **llm-d** needs the GPU inside Kubernetes, so it needs Linux on the PC (dual-boot on a second SSD).
  Then the PC joins k3s as a GPU agent node, vLLM moves into a pod, and you can try llm-d with one real
  vLLM pod plus `llm-d-inference-sim` pods.
- **Agents:** LangGraph or Microsoft Agent Framework against `http://litellm.PI_IP.nip.io/v1`, with
  read-only tools (Kubernetes MCP server, Prometheus queries) and a human approval step.

## 10. Troubleshooting
| Problem | Fix |
|---|---|
| Pi pods can't reach vLLM | From the Pi: `curl http://PC_IP:8000/health`. Check the Windows firewall rule, that the network is "Private", and that Docker Desktop is running. |
| vLLM `CUDA out of memory` at start | Lower `GPU_UTIL` (0.75) or `MAX_MODEL_LEN` (4096). Close GPU-heavy apps. Stop Ollama-GPU. |
| vLLM very slow first start | It's downloading weights into the `hf-cache` volume. Later starts are fast. |
| `could not select device driver "nvidia"` | Update the NVIDIA Windows driver and Docker Desktop; restart both. |
| Qdrant crashes (jemalloc / page size) | The Pi is on the 16K-page kernel. Check `getconf PAGESIZE` = 4096; re-run `00-prepare-pi.sh`. |
| k3s won't start / no memory metrics | `cat /proc/cmdline` must contain `cgroup_enable=memory`. |
| `*.nip.io` doesn't resolve | Some routers block DNS answers with private IPs. Use a public DNS on your laptop, or add lines like `192.168.1.20 webui.192.168.1.20.nip.io` to your hosts file. |
| LiteLLM pod restarting at first start | It runs DB migrations; give it a few minutes. `kubectl -n ai-lab logs deploy/litellm`. |
| Embedding dimension mismatch | You changed the embedding model. Run `python ingest.py --recreate`. |
| Pod `Pending` | `kubectl -n ai-lab describe pod <pod>`. Usually a PVC or memory request issue. |

## 11. Security notes
- Change every default password and key. Never commit `lab.env` or `.env` files to Git.
- Keep everything on your home network. For remote access use Tailscale or WireGuard, not port forwarding.
- vLLM is protected with `--api-key`, but `/metrics` is open. That's fine on a LAN.
- Pin image versions once things work, the same as in production.
