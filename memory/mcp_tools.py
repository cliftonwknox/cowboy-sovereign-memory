"""MCP server exposing `remember_memory` + `memory_search`.

Named `mcp_tools` (NOT `mcp`) so it never shadows the official `mcp` SDK package —
a real bug we hit once. Register with: `claude mcp add cowboy-memory -- \
  <venv>/bin/python -m memory.mcp_tools`
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from memory.capture import remember
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
    return f"Remembered engram {eid}: {summary}"


@server.tool()
def memory_search(query: str, k: int = 5) -> list:
    """Search your sovereign memory for relevant past facts."""
    return search_text(query, k=k)


if __name__ == "__main__":
    server.run()
