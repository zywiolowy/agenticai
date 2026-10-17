"""Shared settings and clients. Configure via environment variables (see rag/.env.example)."""
import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

PI_IP = os.getenv("PI_IP", "192.168.1.20")
GATEWAY_URL = os.getenv("GATEWAY_URL", f"http://litellm.{PI_IP}.nip.io/v1")
GATEWAY_KEY = os.environ.get("LITELLM_KEY", "sk-change-me-master")
QDRANT_URL = os.getenv("QDRANT_URL", f"http://qdrant.{PI_IP}.nip.io:80")  # explicit :80, else the client defaults to 6333
COLLECTION = os.getenv("COLLECTION", "docs")
CHAT_MODEL = os.getenv("CHAT_MODEL", "local-chat")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embed")
TOP_K = int(os.getenv("TOP_K", "5"))


def qdrant() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def gateway_client():
    """OpenAI client pointed at LiteLLM. The langfuse.openai wrapper traces every call automatically."""
    from langfuse.openai import OpenAI  # drop-in replacement for openai.OpenAI

    return OpenAI(base_url=GATEWAY_URL, api_key=GATEWAY_KEY)


def embed(client, texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]
