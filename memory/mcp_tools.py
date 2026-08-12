"""MCP server exposing `remember_memory` + `memory_search`.

Named `mcp_tools` (NOT `mcp`) so it never shadows the official `mcp` SDK package —
a real bug we hit once. Register with: `claude mcp add cowboy-memory -- \
  <venv>/bin/python -m memory.mcp_tools`
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from memory.capture import remember
from memory.embed import EMBED_CAP
from memory.recall import search_text

server = FastMCP("cowboy-sovereign-memory")


@server.tool()
def remember_memory(summary: str, content: str, pinned: bool = False,
                    name_key: str = "", layer: str = "semantic") -> str:
    """Keep something worth remembering across sessions.

    CHOOSE THE LAYER — it decides whether this is permanent:

    - layer="semantic" (default): durable FOREVER. It never decays and is never
      archived. Use it only for what should still be true in a year — standing
      rules, preferences, architecture, hard-won lessons.
    - layer="episodic": ages out on the decay fuse (a few weeks unless recalled).
      Use it for anything whose meaning carries a date — status, progress, session
      state, "where we left off", what shipped today.

    If it would read as stale in a month, it is episodic. Writing status into the
    semantic layer is how a store fills with notes that contradict later reality
    and can never age out.

    Pass name_key (a stable kebab/snake slug) to make the write idempotent:
    re-remembering the same name_key UPDATES that memory (refreshes content/summary/
    embedding) instead of creating a duplicate. Omit it for a fresh memory each call.

    pinned=True exempts a memory from BOTH decay and archiving — standing facts only.
    """
    if layer not in ("semantic", "episodic"):
        raise ValueError(f"layer must be 'semantic' or 'episodic', got {layer!r}")
    eid = remember(summary=summary, content=content, pinned=pinned,
                   name_key=name_key or None, layer=layer)
    # The embedder only sees the first EMBED_CAP characters of summary+content, so
    # anything past it is stored but can never be matched by a search. Say so at the
    # moment of the write — silently keeping unsearchable text is the worse failure.
    overflow = len(summary) + 1 + len(content) - EMBED_CAP
    if overflow > 0:
        return (f"Remembered engram {eid}: {summary}\n"
                f"WARNING: {overflow} characters past the {EMBED_CAP}-char embed cap are "
                f"UNSEARCHABLE. Split this along topic seams into separate memories and "
                f"re-store them; trimming does not help, and appending makes it worse.")
    return f"Remembered engram {eid}: {summary}"


@server.tool()
def forget_memory(engram_id: int) -> str:
    """Remove a memory outright — use when something must not be held at all.

    This is not the same as letting a memory retire. Retirement archives a row: it leaves
    recall but the text is kept and can be restored. Forgetting deletes it, along with its
    archive copy and its recall/link/proposal rows.

    Use it for something captured that should never have been stored — a secret, personal
    data, a fact the human asked to be removed. For memory that is merely finished, do
    nothing: it retires on its own.

    Copies already written to a markdown export or a database backup are outside this
    reach and are not claimed to be removed.
    """
    from memory.config import load
    from memory.store import open_store
    store = open_store(load())
    try:
        removed = store.forget(engram_id)
    finally:
        store.close()
    if not removed:
        return f"No memory {engram_id} to forget."
    return (f"Forgot engram {engram_id} — row, archive copy and child rows removed. "
            "Existing exports and backups still contain it.")


@server.tool()
def memory_search(query: str, k: int = 5) -> list:
    """Search your sovereign memory for relevant past facts."""
    return search_text(query, k=k)


if __name__ == "__main__":
    server.run()
