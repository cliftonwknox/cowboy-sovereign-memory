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
- **Tended, not just filled.** A memory store is not a log. Capture alone degrades it: it
  raises no errors, it simply becomes harder to find anything in until the answer you
  need is present but unreachable. The **`winnow`** skill is how your instance keeps it
  worth having — writing memories that can be found again, and clearing away what has
  finished so the rest can surface.

## Status

**v0.4.0 — early.** Validated on **Linux** (core logic + the real-embedder recall path).
**macOS** is designed-for but **community-unverified** — Mac users, reports welcome.
New in 0.4.0: **retention will not run on a signal that was never recorded** — the guard now
refuses outright when no memory has a last use later than its creation, and `--dry-run` reports
what a pass would archive without archiving it. **Deleting is now separate from retiring**:
`forget_memory` removes a memory and its archive copy, for something that should never have
been stored. See [`CHANGELOG.md`](CHANGELOG.md).

## Install (Claude Code plugin)

```
/plugin marketplace add cliftonwknox/cowboy-sovereign-memory
/plugin install cowboy-sovereign-memory
```
Then tell your Claude instance **`/memory-install`** — it reads the skill + `docs/DESIGN.md`
and walks you through standing up the backend (store, embedder, optional dreamer, hooks,
nightly schedule) and seeding your own notes. Nothing leaves your machine.

## Quickstart (manual)

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
- **`mcp` tools** — `memory/mcp_tools.py` (`remember_memory`, `memory_search`, `forget_memory`).
- **`cron/run_sleep.py`** — the nightly cycle · **`backup/`** — markdown export.
- **`skills/`** — the agent runbook (install + operate) and **`winnow`**, the care
  discipline: how to write a memory that can be found again, and how to clear away what
  has finished so the rest can surface. · **`commands/`** — `/memory-install`,
  `/memory-status`.
- **`scripts/`** — installer, seeder, and schedulers (systemd / launchd / cron).

## The five invariants
1. **Memory never blocks** (recall is time-bounded + fail-open).
2. **Vectors are pinned to their embedder** (never compare across embedders).
3. **The nightly job proposes; it never destroys** (archive = move, not delete).
4. **The durable layer is judged** (nothing permanent without approval).
5. **What is kept is decided by use, not age** (a memory still being recalled survives
   however old; one nothing asks for retires, however recent).

### Why the fifth one changes everything

It means a memory earns its place by being useful, so the good ones need no protection —
they save themselves by being found. It also means the store depends on two habits, not
one. Capture is only half; without the other half a store fills with dated notes that
outlive the work they describe, and an old note claiming to describe the *current* state
goes on contradicting reality indefinitely.

`skills/winnow/SKILL.md` is that other half, and it carries one rule worth reading before
you touch any retention setting: **never enable a rule that decides what is kept until the
signal it reads has actually been recorded.** A signal that was never written makes every
memory look abandoned at once — which is not evidence of abandonment.

---
*Built by a human and his Claude Code instance, as partners. Sovereign by design — yours,
on your own machine.*
