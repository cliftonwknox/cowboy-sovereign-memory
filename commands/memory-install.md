---
description: Guided install of Cowboy Claude's Sovereign Memory — detect hardware, pick a tier, stand it up, wire Claude Code, schedule sleep, and (optionally) seed the user's own notes.
---

Set up **Cowboy Claude's Sovereign Memory** for me, walking me through it.

Use the `cowboy-sovereign-memory` skill and `docs/DESIGN.md`. Specifically:

1. Detect my OS (`uname -s`), total RAM, and whether I have a usable GPU. Tell me what you found.
2. Recommend a tier (Lite / Standard / Full) for my hardware and explain the trade-off. Let me choose.
3. Walk me through `scripts/install.sh` step by step — don't run anything destructive or costly without checking with me first.
4. Wire the recall + extraction hooks into `~/.claude/settings.json` (my real paths) and register the MCP tools.
5. Set up the nightly sleep scheduler for my OS.
6. Verify it works (embedder health, a test remember+search, one sleep cycle) and tell me to restart Claude Code.
7. Ask if I want to seed it from my existing notes.

Keep it conversational. Default to the portable, lower-resource options unless I ask otherwise. Remember: it ships empty and my data never leaves this machine.
