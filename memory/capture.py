"""Capture — the judged durable write. `remember()` IS the judged gate (I4):
anything written here lands in the semantic (durable) layer by deliberate choice.
"""
from __future__ import annotations

from memory.config import load
from memory.embed import embed
from memory.store import open_store


def remember(summary: str, content: str, *, kind: str = "note", pinned: bool = False,
             layer: str = "semantic", origin: str = "judged",
             name_key: str | None = None) -> int:
    cfg = load()
    store = open_store(cfg)
    try:
        vec = embed(f"{summary}\n{content}", cfg, timeout=30)
        return store.write_engram(
            layer=layer, kind=kind, content=content, summary=summary[:512],
            embedding=vec, embed_model_id=cfg.embed_model_id, embed_dim=cfg.embed_dim,
            origin=origin, confidence="pinned" if pinned else "high", pinned=pinned,
            name_key=name_key)
    finally:
        store.close()
