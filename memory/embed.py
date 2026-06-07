"""Embedding — stdlib only (urllib), so it loads instantly on the recall hot path.

Importing a heavy HTTP/LLM client can cost *seconds* just to import; recall must stay
sub-second (I1). Works with a llama.cpp server (`/embedding`) or any OpenAI-style
`/v1/embeddings` endpoint — whatever the human stood up for their embedder.
"""
from __future__ import annotations

import json
import urllib.request


def embed(text: str, cfg, timeout: float | None = None) -> list[float]:
    """Return the embedding vector for `text`. Truncates to a safe length (bge 512-tok cap)."""
    text = (text or "")[:1400]
    secs = (timeout if timeout is not None else cfg.recall_timeout_ms / 1000.0)
    base = cfg.embed_url.rstrip("/")

    # 1) OpenAI-style /v1/embeddings
    try:
        body = json.dumps({"input": text, "model": cfg.embed_model_id}).encode()
        req = urllib.request.Request(base + "/v1/embeddings", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=secs) as r:
            return json.loads(r.read())["data"][0]["embedding"]
    except Exception:
        pass

    # 2) llama.cpp native /embedding
    body = json.dumps({"content": text}).encode()
    req = urllib.request.Request(base + "/embedding", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=secs) as r:
        d = json.loads(r.read())
    if isinstance(d, list):
        d = d[0]
    return d.get("embedding") or d["data"][0]["embedding"]
