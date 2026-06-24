"""Embedding — stdlib only (urllib), so it loads instantly on the recall hot path.

Importing a heavy HTTP/LLM client can cost *seconds* just to import; recall must stay
sub-second (I1). Works with a llama.cpp server (`/embedding`) or any OpenAI-style
`/v1/embeddings` endpoint — whatever the human stood up for their embedder.
"""
from __future__ import annotations

import json
import urllib.request


def embed(text: str, cfg, timeout: float | None = None) -> list[float]:
    """Return the embedding vector for `text`.

    bge is a 512-token model, so the input must fit that budget. A char cap is
    only a rough proxy — token-dense text (git hashes, paths, version strings)
    packs far more tokens per char, so 1400 chars can blow past 512 tokens and
    the embedder rejects the batch. Truncate to decreasing char budgets and
    retry, so any density lands within the cap (the full content still lives in
    the store; only the embedding input is trimmed). Common path = one call.
    """
    text = text or ""
    secs = (timeout if timeout is not None else cfg.recall_timeout_ms / 1000.0)
    last_exc: Exception | None = None
    for cap in (1400, 1000, 700, 500):
        try:
            return _embed_once(text[:cap], cfg, secs)
        except Exception as exc:  # too-large batch / transient — retry shorter
            last_exc = exc
    raise last_exc  # type: ignore[misc]


def _embed_once(text: str, cfg, secs: float) -> list[float]:
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
