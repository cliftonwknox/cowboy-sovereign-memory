"""Round-trippable markdown export — so the human can always read, grep, diff, and
restore their memory in plain text. Their data, in a format they own (privacy §8).
"""
from __future__ import annotations

from pathlib import Path

from memory.config import load
from memory.store import open_store


def export(out_dir) -> int:
    cfg = load()
    store = open_store(cfg)
    try:
        rows = store.export_active()
    finally:
        store.close()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Sovereign Memory — export\n",
             "_Plain-text mirror of the active store. Your memory, readable + portable._\n"]
    cur_layer = None
    for r in rows:
        if r["layer"] != cur_layer:
            cur_layer = r["layer"]
            lines.append(f"\n## {cur_layer.title()}\n")
        lines.append(f"### {r['summary']}\n\n{r['content']}\n\n"
                     f"*(id {r['id']} · {r['origin']} · {r['confidence']} · {r['created_at']})*\n")
    (out / "MEMORY.md").write_text("\n".join(lines))
    return len(rows)
