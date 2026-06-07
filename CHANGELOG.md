# Changelog

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
