# Changelog

## v0.2.0 — 2026-06-09
**Idempotent memory writes** — keep refining a memory without piling up duplicates.

- **`name_key` on `remember` / `remember_memory`** — pass a stable kebab/snake slug and the
  write becomes idempotent: re-remembering the same `name_key` **updates** that memory
  (refreshes content/summary/embedding) instead of creating a duplicate, and lets a memory
  be a `[[name_key]]` link target. Omit it for the previous append-a-fresh-engram behavior.
  The update touches content/summary/embedding **only** — never the self-tending fields
  (salience / recall / state), so reinforcement is preserved.
- **Idempotent `seed.py`** — each markdown section now seeds under a stable `name_key`
  derived from (file, heading), so re-running the seeder over your notes updates rather
  than duplicates.
- **Schema** — `name_key` column + UNIQUE index on the `engram` table in **both** backends
  (sqlite-vec and MariaDB). NULLs are distinct, so unnamed engrams never collide.

**Validation:** `name_key` idempotency (incl. the sqlite-vec two-table vector refresh) and
seed idempotency smoke-tested on **Linux** (sqlite-vec default backend). The MariaDB path is
symmetric get-or-update code.

## v0.1.0 — 2026-06-07
Initial public release. **Cowboy Claude's Sovereign Memory** — a local, private,
self-tending memory for Claude Code.

- **Recall** — proactive, blended rank (cosine + salience + recency), dedup, fail-open + time-bounded (I1).
- **Capture** — `remember` (judged → durable, I4) + end-of-session extraction (auto → episodic, optional tier).
- **Sleep** — nightly: reinforce → decay → expire → archive (move-not-delete, I3) → propose (promote/merge/consolidate) → conflict-detect → markdown backup.
- **Store abstraction** — sqlite-vec (portable default) or MariaDB ≥ 11.7 (power option) behind one interface.
- **Tiered** — Lite (embedder only) / Standard (2B dreamer) / Full (4B dreamer), recommended by hardware.
- **Claude Code plugin** — recall + extraction hooks, MCP tools (`remember_memory`, `memory_search`), the operating skill, `/memory-install` + `/memory-status`.
- **Ships empty; data never leaves the machine.**

**Validation:** core logic + the real-embedder recall path validated on **Linux**.
**macOS** is designed-for but **community-unverified** — reports welcome.
Known tuning follow-ons (see `docs/DESIGN.md` §10): differentiate salience + severity,
make conflict-detect incremental.
