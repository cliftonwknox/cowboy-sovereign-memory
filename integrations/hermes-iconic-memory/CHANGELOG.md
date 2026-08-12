# Changelog — Hermes Iconic Memory

## v2.1 — 2026-08-12

v2.0 corrected the memory model. This revision corrects the parts that decide whether it is safe to
install and run, in the order they constrain each other.

### Fixed — isolation was undefined

Storage paths were hard-coded under a fixed home, which makes separate profiles share one database
silently. Every path now derives from the `hermes_home` passed to `initialize()`.

A store serving a gateway serves several people, so rows now carry an explicit scope — identity,
workspace, platform, user, and an optional conversation or tenant — and **every read and write is
predicated on it**. The filter belongs in the query, not in post-filtering after ranking: a search
that ranks across everyone and then discards the wrong rows has already leaked them into the
ordering. Sharing across scopes is explicit or it does not happen.

### Fixed — provider installation and activation did not match the host

User-installed memory providers are discovered at `$HERMES_HOME/plugins/<name>/`; the previous path
was the layout used for providers bundled inside the distribution. Discovery is a text scan for
`register_memory_provider` or a `MemoryProvider` subclass in `__init__.py`, so a package without one
is skipped in silence. Enabling a plugin also does not select it — the active provider is chosen
through `memory.provider` or the memory setup flow.

### Fixed — retention could run before its signals were proven

The install sequence ran a real maintenance pass while testing reinforcement, then checked retention
safety afterwards, and scheduled recurring maintenance before either. That ordering can trigger the
mass archival the design exists to prevent.

Retention now ships **disabled**. The order is: prove reinforcement with a reinforce-only pass,
confirm last use is being recorded with a dry run, baseline it if not, check the archive-wave guard,
then enable retention, then take one supervised pass, and only then schedule.

### Fixed — extraction could lose its only input

Session end, delegation and compression are exactly when the process is most likely to exit, and the
raw input lived only in RAM. Hooks now persist a keyed job before returning, and a worker leases,
runs, and writes results idempotently, with bounded retries and lease recovery after a crash.

Pre-compression is the exception: it must preserve synchronously within its return contract, because
enqueuing and returning saves nothing if compression proceeds immediately.

### Fixed — described as a replacement when it is additive

Native memory keeps being written and injected. Each layer now has a stated job and authority:
identity and bootstrap facts stay in the bounded always-injected files, while the provider owns the
unbounded corpus injected by relevance. Whether native writes mirror into the provider is a decision
to make explicitly, with provenance and stable keys if taken.

### Fixed — "nothing is deleted" was the wrong promise for deletion

Archival hides a row from recall; it does not remove it from the database, exports, or backups. That
is right for retirement and wrong for a captured secret or a deletion request. Archive, restore and
forget are now separate operations, and forget states its blast radius — primary row, vector index,
consolidated descendants, proposal and conflict records, exports, backups — with a tombstone
recording that a deletion happened without retaining what was deleted. What cannot be purged is
stated as a limitation rather than omitted.

### Changed — provider-owned tool names

`remember` / `recall` / `forget` are broad enough to collide in an extensible runtime, and the losing
side of a collision fails in ways that are hard to attribute. Tools are now `iconic_*`.

### Changed — status

The pack is a design, not an installation guide, and says so. Install commands are POSIX; the
preflight's macOS and Windows paths are best-effort and unverified.

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

### Documented — queues that nothing drains

Promotion, merge and conflict proposals accumulate indefinitely when no code reads a decision. The
design now requires naming the consumer before filing work for later, and giving every queued row a
stable key checked *before* the expensive model call — rows keyed on columns left NULL never collide,
so a de-duplicating index silently does nothing and the same work is proposed again every night.

**This is a stated requirement, not a built consumer.** Until a review interface and a decision state
machine exist, proposal queues should be deferred from a first implementation rather than shipped
with nothing to drain them.

### Changed — writes choose their layer

`remember` takes a layer, so status and session state can age out instead of being permanent by
default.

## v1.0

Initial design, overview, and install runbook: a `MemoryProvider` plugin giving Hermes semantic
recall, auto-extraction, a tiered store, and a sleep cycle.
