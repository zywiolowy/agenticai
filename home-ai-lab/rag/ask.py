"""Ask: question -> embed -> Qdrant search (optionally filtered) -> prompt -> vLLM answer with citations.
Every step is traced in Langfuse as one nested trace (retrieve span + generation).

    python ask.py "How do I roll back a deployment?"
    python ask.py "How do I roll back a deployment?" --team engineering --k 3
"""
import argparse

from langfuse import get_client, observe
from qdrant_client.models import FieldCondition, Filter, MatchValue

from common import CHAT_MODEL, COLLECTION, TOP_K, embed, gateway_client, qdrant

SYSTEM = (
    "You are an internal engineering assistant. Answer ONLY from the context below. "
    "Cite sources as [source#chunk]. If the context does not contain the answer, say "
    "\"I don't know based on the available documents.\""
)


@observe(name="retrieve")
def retrieve(question: str, k: int, team: str | None) -> list[dict]:
    llm, db = gateway_client(), qdrant()
    qvec = embed(llm, [question])[0]
    flt = Filter(must=[FieldCondition(key="team", match=MatchValue(value=team))]) if team else None
    hits = db.query_points(COLLECTION, query=qvec, limit=k, query_filter=flt, with_payload=True).points
    return [{"score": round(h.score, 3), **h.payload} for h in hits]


@observe(name="rag-answer")
def answer(question: str, k: int = TOP_K, team: str | None = None) -> dict:
    lf = get_client()
    lf.update_current_trace(tags=["rag", "lab"], metadata={"k": k, "team": team})

    docs = retrieve(question, k, team)
    context = "\n\n".join(f"[{d['source']}#{d['chunk']}] {d['text']}" for d in docs)

    llm = gateway_client()
    resp = llm.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.1,
        max_tokens=600,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return {
        "answer": resp.choices[0].message.content,
        "sources": [f"{d['source']}#{d['chunk']} ({d['score']})" for d in docs],
        "trace_id": lf.get_current_trace_id(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--k", type=int, default=TOP_K)
    ap.add_argument("--team", default=None)
    args = ap.parse_args()

    out = answer(args.question, args.k, args.team)
    print(out["answer"])
    print("\nSources:", *out["sources"], sep="\n  ")
    print(f"\nLangfuse trace: {out['trace_id']}")
    get_client().flush()


if __name__ == "__main__":
    main()
