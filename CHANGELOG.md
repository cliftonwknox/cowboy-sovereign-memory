# Changelog

## v0.3.0 — 2026-08-12
**Memories are kept by use, not age** — plus the repairs that made that safe to switch on.

### Changed — read this before upgrading
- **Retention now keys off last use.** A memory untouched for its layer's window is
  archived however old or new it is; one still being recalled survives indefinitely.
  Working state gets weeks, durable knowledge months, and pinned memories are exempt.
  Salience still *orders* search results but no longer decides what is kept. Archiving
  still moves rather than deletes, and now copies the key, dates and a reason so any of
  it can be restored.
- **Before enabling this on an existing store, baseline the last-use column.** If it was
  never written, every memory falls back to its creation date and the whole store looks
  abandoned at once. The nightly job refuses to archive an unusually large wave and says
  so rather than acting on it.

### Fixed
- **Recall reinforcement never worked.** The recall log insert failed on every call and
  the error was swallowed, so no memory's salience could ever rise and decay ran as a
  pure age clock. Explicit searches now feed reinforcement too — previously only the
  prompt hook did.
- **The nightly pass re-proposed the same consolidations every night.** Proposals were
  written with null keys, which never collide in a unique index, so a cluster already
  awaiting judgement was proposed again on the next run — at the cost of a model call
  each. Proposals are now anchored to their cluster and checked before the model runs.
- **Conflict detection could not see time.** Comparing two undated summaries made a later
  status read as a contradiction of an earlier one. Notes now carry their dates.
- **Reviews counted decided items as outstanding**, so a worked queue never looked worked.

### Added
- **`skills/winnow`** — the care discipline: writing a memory that can be found again,
  clearing away what has finished, and repairing many memories at once without losing
  anything.
- **A nightly self-check.** Deterministic checks run after the cognitive stages: mechanical
  faults are repaired outright, anything needing judgement is filed as one dated report.
  Every check is stateless, so an unresolved finding is re-measured the next night.
- **Writes choose their layer.** `remember_memory` takes `layer="semantic"|"episodic"`, so
  status and session state can age out instead of being permanent by default.
- **Over-cap writes now warn.** Text past the embed cap is stored but can never be matched
  by a search; the write tool reports the overflow it just created.
- **Backup locations are configured**, not assumed, via `CCSM_BACKUP_DIRS` and
  `CCSM_BACKUP_VAULT`. Unset means the check is skipped.

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
