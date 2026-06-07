# Privacy Policy — Cowboy Claude's Sovereign Memory

_Last updated: 2026-06-07 · Plugin version: 0.1.0_

**Short version: this plugin collects nothing, transmits nothing, and phones home to no one. Your memory lives entirely on your own machine, under your control.**

## What data the plugin handles
The plugin stores the memories you (or your Claude Code instance) choose to keep — short text notes and their vector embeddings — in a **local database on your machine**: a SQLite file by default (`sqlite-vec`), or a MariaDB instance you run yourself. That's it.

## What it does NOT do
- **No telemetry, analytics, tracking, or usage reporting** — none, ever.
- **No data sent to the plugin's authors, to Anthropic, or to any third party.** The plugin contacts no servers of ours; we operate none.
- **No accounts, no API keys to us, no cloud sync.**
- **Ships empty** — it contains no one else's data, and yours is never uploaded anywhere.

## Network activity
The plugin's only network calls are to the **embedding and (optional) language-model endpoints you configure** — which **default to your own local machine** (`localhost`, e.g. a local `llama.cpp` server).

> If *you* choose to point it at a **remote** embedding/LLM endpoint (by setting `CCSM_EMBED_URL` / `CCSM_DREAMER_URL` to a non-local address), then the text being embedded or summarized is sent to **that endpoint you selected** — exactly as you configured. The plugin never selects, defaults to, or routes through any remote service on its own.

## Your control
- Everything is stored locally; **delete the database file (SQLite) or drop the schema (MariaDB) and it's gone**, with no residue elsewhere.
- A nightly **plain-text markdown export** lets you read, search, diff, and back up your own memory in a format you own.
- The plugin is **open source (MIT)** — every line is auditable in this repository.

## Contact
Questions or concerns: open an issue at
<https://github.com/cliftonwknox/cowboy-sovereign-memory/issues>.

---
*Sovereign by design: your data, your machine, your call.*
