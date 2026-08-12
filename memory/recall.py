"""Recall — proactive, blended, fail-open. The keystone: it NEVER blocks the prompt (I1).

Relevance is not just similarity: score = w_cosine·cosine + w_salience·salience +
w_recency·recency. We run the whole thing in a worker thread with a hard wall-clock
budget; if it overruns or errors, we return nothing and the prompt proceeds untouched.
"""
from __future__ import annotations

import concurrent.futures
import datetime as _dt
from difflib import SequenceMatcher

from memory.config import load
from memory.embed import embed
from memory.store import open_store


def _recency(last_recalled_at: str | None) -> float:
    if not last_recalled_at:
        return 0.0
    try:
        t = _dt.datetime.fromisoformat(str(last_recalled_at).replace("T", " ").split(".")[0])
        age_days = max(0.0, (_dt.datetime.now() - t).total_seconds() / 86400.0)
        return pow(2.718281828, -age_days / 30.0)        # ~1 today, ~0.37 at 30d
    except Exception:
        return 0.0


def _rank(cands, cfg):
    scored = []
    for c in cands:
        s = cfg.w_cosine * c.cosine + cfg.w_salience * min(c.salience, 1.0) \
            + cfg.w_recency * _recency(c.last_recalled_at)
        scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _dedup(scored, threshold):
    kept = []
    for s, c in scored:
        if any(SequenceMatcher(None, c.summary.lower(), k.summary.lower()).ratio() >= threshold
               for _, k in kept):
            continue
        kept.append((s, c))
    return kept


def _body(prompt: str, cfg) -> list[dict]:
    store = open_store(cfg)
    try:
        qvec = embed(prompt, cfg)
        cands = store.search(qvec, cfg.embed_model_id, k=cfg.top_k * 3)
        ranked = _dedup(_rank(cands, cfg), cfg.dedup_threshold)[: cfg.top_k]
        out = []
        for score, c in ranked:
            try:
                store.log_recall(c.id, score)         # best-effort reinforcement signal
            except Exception:
                pass
            g = store.get(c.id) or {}
            out.append({"id": c.id, "summary": c.summary, "layer": g.get("layer", "")})
        return out
    finally:
        store.close()


def recall(prompt: str) -> list[dict]:
    """Top-K relevant memories for `prompt`. Fail-open + time-bounded (I1)."""
    cfg = load()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_body, prompt, cfg).result(timeout=cfg.recall_timeout_ms / 1000.0)
    except Exception:
        return []                                      # slow or broken → inject nothing


def search_text(query: str, k: int = 5) -> list[dict]:
    """Synchronous text search for the MCP tool (no time budget — explicit lookup)."""
    cfg = load()
    store = open_store(cfg)
    try:
        cands = store.search(embed(query, cfg, timeout=30), cfg.embed_model_id, k=k)
        for c in cands:
            try:
                store.log_recall(c.id, c.cosine)  # best-effort reinforcement signal
            except Exception:
                pass
        return [{"id": c.id, "summary": c.summary, "content": c.content,
                 "cosine": round(c.cosine, 3)} for c in cands]
    finally:
        store.close()
