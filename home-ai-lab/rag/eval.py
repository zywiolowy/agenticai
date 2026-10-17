"""Evaluate the RAG pipeline against a golden set and push scores to Langfuse.
Exits with code 1 if quality is below threshold -> use it as a CI gate (GitLab/Jenkins).

    python eval.py                      # uses golden.jsonl
    python eval.py --min-hit 0.8 --judge

Metrics:
  hit@k      – was the expected source document among the retrieved chunks? (retrieval quality)
  keywords   – share of expected keywords present in the answer (cheap answer check)
  judge      – optional LLM-as-a-judge: is the answer supported by the sources? (faithfulness, 0/1)
"""
import argparse
import json
import sys

from langfuse import get_client

from ask import answer
from common import CHAT_MODEL, gateway_client

JUDGE_PROMPT = (
    "You grade a RAG answer. Reply with only 1 or 0.\n"
    "1 = the answer is correct for the question and does not invent facts.\n"
    "0 = the answer is wrong, unsupported, or hallucinated.\n\n"
    "Question: {q}\nExpected facts: {exp}\nAnswer: {a}"
)


def judge(q: str, expected: list[str], a: str) -> float:
    r = gateway_client().chat.completions.create(
        model=CHAT_MODEL, temperature=0, max_tokens=3,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(q=q, exp=", ".join(expected), a=a)}],
    )
    return 1.0 if r.choices[0].message.content.strip().startswith("1") else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="golden.jsonl")
    ap.add_argument("--min-hit", type=float, default=0.7)
    ap.add_argument("--judge", action="store_true")
    args = ap.parse_args()

    lf = get_client()
    rows = [json.loads(line) for line in open(args.file, encoding="utf-8") if line.strip()]
    hits, kw_scores, judge_scores = [], [], []

    for r in rows:
        out = answer(r["question"])
        hit = float(any(s.startswith(r["expected_source"]) for s in out["sources"]))
        ans = out["answer"].lower()
        kw = sum(k.lower() in ans for k in r["expected_keywords"]) / max(len(r["expected_keywords"]), 1)
        hits.append(hit)
        kw_scores.append(kw)
        lf.create_score(trace_id=out["trace_id"], name="hit_at_k", value=hit)
        lf.create_score(trace_id=out["trace_id"], name="keyword_match", value=kw)
        line = f"hit={hit:.0f} kw={kw:.2f}"
        if args.judge:
            j = judge(r["question"], r["expected_keywords"], out["answer"])
            judge_scores.append(j)
            lf.create_score(trace_id=out["trace_id"], name="judge_faithful", value=j)
            line += f" judge={j:.0f}"
        print(f"{line}  | {r['question']}")

    lf.flush()
    hit_rate = sum(hits) / len(hits)
    print(f"\nhit@k={hit_rate:.2f}  keyword_match={sum(kw_scores)/len(kw_scores):.2f}", end="")
    if judge_scores:
        print(f"  judge={sum(judge_scores)/len(judge_scores):.2f}", end="")
    print()
    if hit_rate < args.min_hit:
        print(f"FAIL: hit@k {hit_rate:.2f} < {args.min_hit}")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
