# Cowboy Claude's Sovereign Memory 🤠

![Cowboy Claude's Sovereign Memory](docs/social-card.png)

A **local, private, self-tending memory for Claude Code** — recall that surfaces what's
relevant, capture that keeps what matters, and a nightly *sleep* that reinforces the
useful, lets the trivial fade, and abstracts recurring details into durable lessons.

- **Sovereign.** Everything runs on *your* machine. No cloud, no telemetry, no transmission.
- **Ships empty.** It never contains anyone else's memories. It fills with *yours*.
- **Tiered.** Runs on a laptop (sqlite-vec + a tiny embedder, no dreamer) or a workstation
  (MariaDB + a 4B dreamer). Pick by your hardware.
- **Built for Claude to install.** The included skill lets *your* Claude Code instance
  detect your setup, recommend a tier, stand it up, and seed it — conversationally.

## Quickstart

> The intended path: ask your Claude Code instance to **`/memory-install`** (or "set up my
> sovereign memory") — it will read the skill + `docs/DESIGN.md` and walk you through it.

Manual:
```bash
scripts/install.sh                  # venv + deps + store schema (sqlite-vec)
# serve a small embedder GGUF on :8900 (llama.cpp); optionally a dreamer on :8901
# wire the hooks + MCP (the skill does this), schedule scripts/scheduler/*, restart Claude Code
.venv/bin/python scripts/seed.py MEMORY.md   # optional: seed from your own notes
```

## What's here
- **`docs/DESIGN.md`** — the full, OS/processor-agnostic design + runbook (read this).
- **`memory/`** — the library: `store` (sqlite-vec ↔ MariaDB), `embed`, `recall`,
  `capture`, `dreamer`, `extract`, `sleep`.
- **`hooks/`** — `user_prompt_submit` (recall) · `session_end` (extraction).
- **`mcp` tools** — `memory/mcp_tools.py` (`remember_memory`, `memory_search`).
- **`cron/run_sleep.py`** — the nightly cycle · **`backup/`** — markdown export.
- **`skills/` + `commands/`** — the agent runbook + `/memory-install`, `/memory-status`.
- **`scripts/`** — installer, seeder, and schedulers (systemd / launchd / cron).

## The four invariants
1. **Memory never blocks** (recall is time-bounded + fail-open).
2. **Vectors are pinned to their embedder** (never compare across embedders).
3. **The nightly job proposes; it never destroys** (archive = move, not delete).
4. **The durable layer is judged** (nothing permanent without approval).

---
*Built by a human and his Claude Code instance, as partners. Sovereign by design — yours,
on your own machine.*
