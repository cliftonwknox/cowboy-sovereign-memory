"""SessionEnd extraction job — read a transcript, extract durable facts, store them.

Run detached by the SessionEnd hook so it never delays session close. Defensive JSONL
parsing (transcripts vary); chunks the TAIL of long sessions (recent context matters
most) to bound dreamer work.
"""
from __future__ import annotations

import json
import sys

from memory.config import load
from memory.extract import encode_candidates, extract_candidates
from memory.store import open_store


def read_transcript_text(path: str) -> str:
    parts = []
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    parts.append(line)
                    continue
                msg = obj.get("message") or obj
                content = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "text":
                            parts.append(blk.get("text", ""))
    except Exception:
        return ""
    return "\n".join(parts)


def chunk(text: str, size: int = 12000, max_chunks: int = 15) -> list[str]:
    chunks = [text[i:i + size] for i in range(0, len(text), size)]
    return chunks[-max_chunks:]                          # tail: most-recent context


def main() -> None:
    if len(sys.argv) < 2:
        return
    cfg = load()
    if not cfg.has_dreamer:
        return                                          # Lite tier: no cognition
    text = read_transcript_text(sys.argv[1])
    if len(text) < 100:
        return
    store = open_store(cfg)
    try:
        total = 0
        for ch in chunk(text):
            total += encode_candidates(extract_candidates(ch, cfg), cfg, store)
        print(f"extracted {total} episodic memories")
    finally:
        store.close()


if __name__ == "__main__":
    main()
