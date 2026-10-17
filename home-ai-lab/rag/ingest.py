"""Ingest: read docs -> chunk by heading -> embed (Pi Ollama via LiteLLM) -> upsert into Qdrant.

    python ingest.py               # ingest ./docs
    python ingest.py --path ~/notes --team platform
    python ingest.py --recreate    # drop and rebuild the collection

Re-running is safe: chunk IDs are deterministic (uuid5 of source + chunk number + text hash),
so unchanged chunks are overwritten, not duplicated.
"""
import argparse
import hashlib
import re
import uuid
from pathlib import Path

from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

from common import COLLECTION, embed, gateway_client, qdrant

MAX_CHARS = 2000      # ~500 tokens
OVERLAP = 200


def chunk_markdown(text: str) -> list[dict]:
    """Structure-aware chunking: split on headings, then cap size with overlap."""
    sections, current, heading = [], [], ""
    for line in text.splitlines():
        if re.match(r"^#{1,4} ", line):
            if current:
                sections.append((heading, "\n".join(current).strip()))
            heading, current = line.lstrip("# ").strip(), [line]
        else:
            current.append(line)
    if current:
        sections.append((heading, "\n".join(current).strip()))

    chunks = []
    for heading, body in sections:
        if not body:
            continue
        start = 0
        while start < len(body):
            piece = body[start:start + MAX_CHARS]
            chunks.append({"heading": heading, "text": piece})
            if start + MAX_CHARS >= len(body):
                break
            start += MAX_CHARS - OVERLAP
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="docs")
    ap.add_argument("--team", default="engineering", help="metadata used for filtered search / ACL demo")
    ap.add_argument("--recreate", action="store_true")
    args = ap.parse_args()

    files = [p for p in Path(args.path).expanduser().rglob("*") if p.suffix in {".md", ".txt"}]
    if not files:
        raise SystemExit(f"No .md/.txt files in {args.path}")

    llm, db = gateway_client(), qdrant()
    dim = len(embed(llm, ["dimension probe"])[0])

    if args.recreate and db.collection_exists(COLLECTION):
        db.delete_collection(COLLECTION)
    if not db.collection_exists(COLLECTION):
        db.create_collection(COLLECTION, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        # Index the fields we filter on, so filtered search stays fast
        db.create_payload_index(COLLECTION, "team", PayloadSchemaType.KEYWORD)
        db.create_payload_index(COLLECTION, "source", PayloadSchemaType.KEYWORD)
        print(f"Created collection '{COLLECTION}' (dim={dim}, cosine)")

    total = 0
    for f in files:
        chunks = chunk_markdown(f.read_text(encoding="utf-8", errors="ignore"))
        if not chunks:
            continue
        vectors = embed(llm, [c["text"] for c in chunks])
        points = []
        for i, (c, v) in enumerate(zip(chunks, vectors)):
            h = hashlib.sha1(c["text"].encode()).hexdigest()[:12]
            pid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{f}:{i}:{h}"))
            points.append(PointStruct(id=pid, vector=v, payload={
                "source": f.name, "heading": c["heading"], "chunk": i,
                "team": args.team, "text": c["text"],
            }))
        db.upsert(COLLECTION, points=points)
        total += len(points)
        print(f"  {f.name}: {len(points)} chunks")

    print(f"Done: {total} chunks from {len(files)} files -> {COLLECTION}")
    print("Browse them in the Qdrant dashboard: http://qdrant.<PI_IP>.nip.io/dashboard")


if __name__ == "__main__":
    main()
