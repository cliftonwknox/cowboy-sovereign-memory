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
                    name_key: str = "") -> str:
    """Keep a durable fact worth remembering across sessions (judged → semantic layer).

    Pass name_key (a stable kebab/snake slug) to make the write idempotent:
    re-remembering the same name_key UPDATES that memory (refreshes content/summary/
    embedding) instead of creating a duplicate. Omit it for a fresh memory each call.
    """
    eid = remember(summary=summary, content=content, pinned=pinned,
                   name_key=name_key or None)
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
def memory_search(query: str, k: int = 5) -> list:
    """Search your sovereign memory for relevant past facts."""
    return search_text(query, k=k)


if __name__ == "__main__":
    server.run()
