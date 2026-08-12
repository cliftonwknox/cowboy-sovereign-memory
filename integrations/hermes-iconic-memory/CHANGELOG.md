# Changelog — Hermes Iconic Memory

## v2.0 — 2026-08-12

The v1 documents described a memory engine as designed. This revision describes one that has been
run continuously, and corrects the places where practice disagreed with the plan.

### Changed — retention

- **What is kept is decided by last use, not age.** A memory untouched for its layer's window is
  archived however old or new it is; one still being recalled survives indefinitely. Working state
  gets weeks, durable knowledge months, pinned memories never expire. Salience and decay still
  *order* search results but no longer decide what survives.
- **A decay-to-floor rule retires the wrong memories.** Because the clock starts at writing, it
  discards things still in daily use while keeping recent ones nothing ever asks for.

### Added — the law that makes retention safe

**Never enable a rule that decides what is kept until the signal it reads has actually been
recorded.** If the last-use column has never been written — a silently swallowed exception on the
recall path is enough — every memory falls back to its creation date and the whole store looks
abandoned at once. Baseline the signal first, then enable the rule. The sleep job must refuse an
unusually large archive wave and report it rather than act on it.

### Added — the embed cap

The embedder sees only the first *N* characters of a memory. **Text past that is stored and readable
but can never be matched by a search**, and it raises no error. The design now requires a warning at
the point of writing, splitting at topic seams rather than trimming or appending, and summaries that
read like the query someone would later type.

### Added — nightly self-check

Deterministic checks (no model call) run after the cognitive stages: mechanical faults are repaired
outright, everything needing judgement is filed as one dated report. The checks are stateless, so an
unresolved finding is re-measured the next night — which is what makes the report itself safe to let
age out.

### Added — `winnow-SKILL.md` as a shipped file

The bundled skill was a paragraph inside the design. It is now a file the installer copies into the
agent's skills directory, covering planting (layer, summary, cap, keys, splitting), winnowing
(retention, triage, supersession), and repairing many memories at once. A store degrades quietly
without it.

### Added — install verifications for the two silent failures

The runbook now proves, by observation, that reinforcement actually raises a salience and that last
use is being recorded before retention is switched on. Both failures otherwise look exactly like
success.

### Fixed — queues that nothing drains

Promotion, merge and conflict proposals accumulate indefinitely when no code reads a decision. The
design now requires naming the consumer before filing work for later, and giving every queued row a
stable key checked *before* the expensive model call — rows keyed on columns left NULL never collide,
so a de-duplicating index silently does nothing and the same work is proposed again every night.

### Changed — writes choose their layer

`remember` takes a layer, so status and session state can age out instead of being permanent by
default.

## v1.0

Initial design, overview, and install runbook: a `MemoryProvider` plugin giving Hermes semantic
recall, auto-extraction, a tiered store, and a sleep cycle.
