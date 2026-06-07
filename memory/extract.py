"""Extraction — the dreamer pulls durable facts from text; dedup-on-write to episodic.

Keep sane, durable facts (decisions, preferences, lessons, state) — NOT chit-chat or
ephemeral trivia. Each kept fact is embedded and written to the episodic layer with
origin=auto_extracted, skipping anything near-identical to what's already stored.
"""
from __future__ import annotations

from memory import dreamer
from memory.embed import embed

_SYS = (
    "Extract durable facts worth remembering from the text. Keep decisions, preferences, "
    "lessons, project state, and identity facts. SKIP chit-chat, pleasantries, and "
    "ephemeral trivia (exact byte sizes, version hashes). Output ONLY a JSON array of "
    'objects: [{"summary": one short sentence, "content": a fuller sentence or two}]. '
    "Return [] if nothing is worth keeping."
)

DEDUP_COS = 0.92


def extract_candidates(text: str, cfg) -> list[dict]:
    raw = dreamer.chat(_SYS, text[:12000], cfg, max_tokens=800)
    out = []
    for c in dreamer.extract_json_array(raw):
        if isinstance(c, dict) and c.get("summary") and c.get("content"):
            out.append({"summary": str(c["summary"])[:512], "content": str(c["content"])})
    return out


def encode_candidates(cands: list[dict], cfg, store) -> int:
    written = 0
    for c in cands:
        vec = embed(f"{c['summary']}\n{c['content']}", cfg, timeout=30)
        hits = store.search(vec, cfg.embed_model_id, k=1)
        if hits and hits[0].cosine >= DEDUP_COS:
            continue                                    # near-duplicate already stored
        store.write_engram(
            layer="episodic", kind="note", content=c["content"], summary=c["summary"],
            embedding=vec, embed_model_id=cfg.embed_model_id, embed_dim=cfg.embed_dim,
            origin="auto_extracted", confidence="medium")
        written += 1
    return written
