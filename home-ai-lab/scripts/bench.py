"""Load test vLLM directly to see continuous batching in action.

    pip install openai
    python bench.py --url http://192.168.1.10:8000/v1 --key change-me-vllm-key --model qwen2.5-7b

For each concurrency level it fires N parallel streaming requests and reports:
  TTFT p50/p95  – time to first token (what users feel)
  tok/s per req – speed of one stream
  total tok/s   – throughput of the whole GPU (this should grow a lot with concurrency)
Run it once against vLLM and once against Ollama (http://PC_IP:11434/v1, any key) to compare.
"""
import argparse
import asyncio
import statistics
import time

from openai import AsyncOpenAI

PROMPT = "Explain in about 200 words how Kubernetes schedules a pod onto a node."


async def one(client, model, max_tokens):
    t0 = time.perf_counter()
    ttft, n = None, 0
    stream = await client.chat.completions.create(
        model=model, max_tokens=max_tokens, temperature=0.7, stream=True,
        messages=[{"role": "user", "content": PROMPT}],
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            if ttft is None:
                ttft = time.perf_counter() - t0
            n += 1  # ~1 token per chunk
    total = time.perf_counter() - t0
    return ttft or total, n, total


async def run(args):
    client = AsyncOpenAI(base_url=args.url, api_key=args.key)
    print(f"{'conc':>4} {'TTFT p50':>9} {'TTFT p95':>9} {'tok/s/req':>10} {'total tok/s':>12}")
    for c in args.levels:
        t0 = time.perf_counter()
        res = await asyncio.gather(*[one(client, args.model, args.max_tokens) for _ in range(c)])
        wall = time.perf_counter() - t0
        ttfts = sorted(r[0] for r in res)
        per_req = statistics.mean(r[1] / max(r[2] - r[0], 1e-6) for r in res)
        total_tps = sum(r[1] for r in res) / wall
        p95 = ttfts[min(len(ttfts) - 1, int(0.95 * len(ttfts)))]
        print(f"{c:>4} {statistics.median(ttfts):>8.2f}s {p95:>8.2f}s {per_req:>10.1f} {total_tps:>12.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--key", default="none")
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 4, 8, 16])
    asyncio.run(run(ap.parse_args()))
