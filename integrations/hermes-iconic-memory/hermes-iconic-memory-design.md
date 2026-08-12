# Hermes Iconic Memory — Design

**What:** a drop-in `MemoryProvider` plugin for Hermes Agent that replaces the tiny
hand-curated flat-file memory with a self-tending, vector-recalled, auto-extracting memory —
the Cowboy-Memory architecture, repackaged and slimmed for other people's machines.
**Who:** friends who run Hermes and want real cross-session memory without standing up a DB
cluster or a GPU rig. **Author target:** zero-ops by default, power-ops by opt-in.
**Name:** *Iconic Memory* — borrowed from the cognitive term for the brief high-fidelity
sensory buffer; here it names the freshest tier that feeds recall (see Tiers below).

> Runbook stance (§0 bar-commit): this is a DESIGN. The bar is *grounded + implementable + fits
> the real plug-in seam*, not "looks plausible." Both source systems were read before designing;
> every integration point below maps to a real method in Hermes' `MemoryProvider` ABC. No code is
> written until this design is approved (brainstorming HARD-GATE).

---

## 1. Examination — Hermes' memory (from source, `~/.hermes-source`)

**Native memory is deliberately tiny and manual:**
- Two flat files in `~/.hermes/memories/`: `MEMORY.md` (~2,200 chars / ~800 tok, agent notes) and
  `USER.md` (~1,375 chars / ~500 tok, user profile).
- **Frozen-snapshot injection:** both are rendered into the system prompt **once at session start**
  and never change mid-session (to preserve the LLM prefix cache). Mid-session writes persist to
  disk but only surface next session.
- The agent self-curates via a `memory` tool (add / replace / remove); when full it must
  consolidate to make room. Entries split by `§`.
- **No vectors, no semantic recall, no auto-extraction, no consolidation engine.** It's a ~1,300-token
  notebook the model hand-edits. Fine for "who you are"; useless for a working corpus.

**The sanctioned extension point (this is the whole foundation):** Hermes ships a
**`MemoryProvider` plugin** system (`plugins/memory/<name>/`, single-select, managed via
`hermes plugins`). A plugin subclasses `agent/memory_provider.py:MemoryProvider`. The contract:

| Method | Role | Iconic uses it for |
|---|---|---|
| `name()` / `is_available()` (abstract, **no network**) | identity + activation gate | report ready; check DB+model present |
| `initialize(session_id, **kw)` (abstract) | per-session setup | open DB, warm embedder, seed iconic buffer |
| `get_tool_schemas()` (abstract) | tools exposed to the agent | `remember`, `recall`, `forget`, `pin` |
| `handle_tool_call(name, args)` | run those tools | active memory management |
| `system_prompt_block()` | the frozen start-of-session block | top consolidated facts (bounded) |
| `prefetch(query, session_id)` / `queue_prefetch(...)` | **live recall** | semantic vector recall per query |
| `sync_turn(user, assistant, session_id)` | per-turn callback | push turn into iconic buffer |
| `on_turn_start(turn, message)` | turn hook | fire `queue_prefetch` for the turn |
| `on_session_end(messages)` | session hook | **dreamer extraction** of the session |
| `on_delegation(task, result)` | subagent hook | extract from delegated work too |
| `on_pre_compress(messages)` | context-compaction hook | salvage salient facts before they're dropped |
| `get_config_schema()` / `save_config()` | config UI | DB choice, model paths, CPU pinning, thresholds |
| `register_cli(subparser)` | add CLI verbs | `hermes iconic sleep|stats|export|doctor` |
| `register(ctx)` + `plugin.yaml hooks:` | wiring | declare the hooks above |

The native system's gaps map **exactly** onto what this seam lets a plugin add: `prefetch`/
`on_turn_start` give **live semantic recall** (native has none); `sync_turn`/`on_session_end`/
`on_delegation`/`on_pre_compress` give **auto-capture** (native is manual-only); `register_cli`
gives a **sleep/maintenance** surface. So Iconic Memory is additive, not a fork.

## 2. Overview — Cowboy Memory (from `~/cowboy-memory`)

A sovereign, self-tending, human-shaped memory engine:
- **Store:** one `engram` table — `layer` (episodic | semantic), `kind`, `content`, `summary`,
  `embedding` (MariaDB native `VECTOR`), `salience`, `recall_count`, `last_recalled_at`, `state`
  (active | stale | archived), `pinned`, `name_key`, `origin`, `why`, timestamps.
- **Recall:** `VEC_DISTANCE_COSINE` over the active set, blended score ≈ **0.6·cosine + 0.25·salience
  + 0.15·recency**, dedup at cosine ≥ 0.97, **fail-open** with a ~400 ms budget (recall never blocks
  the turn). Pinned/relevance-independent rows can ride along.
- **Capture:** a SessionEnd hook runs a **dreamer** (Gemma, CPU, off-GPU) that reads the session and
  extracts durable facts, **dedup-writing** them into the *episodic* scratch (`origin=auto_extracted`).
- **Sleep (nightly + on demand):** **reinforce** salience from the recall log; **decay** unpinned
  rows (ordering only); **archive by last use** — a row untouched for its layer's window moves out,
  however old or new, while one still being recalled stays; **archive = move-not-delete** (state
  transition, never lose data); **consolidate** clusters related-but-distinct episodics (cosine in
  **[0.85, 0.97]**) into semantic; **judged promote/merge** proposals + **conflict-detect**, both
  adjudicated by the dreamer; a deterministic **self-check** that repairs mechanical faults and files
  the rest as one dated report.
- **Compute is stateless + shared:** an embedder server + a Gemma dreamer; the **DB is the per-agent
  privacy boundary**. Round-trippable markdown export for backup.

Two engines (embedder, dreamer) on CPU; one store. That's the shape we slim for friends.

---

## 3. Iconic Memory — the design

### 3.1 Shape
A single Python package shipped as a Hermes memory-provider plugin
(`$HERMES_HOME/plugins/hermes-iconic-memory/` when user-installed; `plugins/memory/<name>/` when
bundled). It carries the Cowboy engine internally but **in-process**
and **single-binary-friendly** — no socket servers required for the default install.

### 3.2 Three tiers (honoring the name)
- **Iconic** — a small in-RAM ring of the last *N* turns (raw, high fidelity, no LLM). Feeds recall
  context and the dreamer; never persisted as-is. The "sensory buffer."
- **Episodic** — auto-extracted durable facts (DB, `layer=episodic`), decaying scratch.
- **Semantic** — consolidated, reinforced, long-term facts (DB, `layer=semantic`), the recall core.
Promotion flows iconic → (dreamer extract) → episodic → (sleep consolidate) → semantic.

### 3.2a Isolation — whose memory is this?

Two boundaries have to hold, and neither is optional once this runs anywhere but one laptop.

**Profile isolation — never hard-code a home.** Every path derives from the `hermes_home` handed to
`initialize()`:

```
$HERMES_HOME/iconic/memory.db
$HERMES_HOME/iconic/config.yaml
$HERMES_HOME/iconic/models/
```

A fixed `~/.hermes` makes separate profiles share one database, silently. Profiles exist precisely to
keep state apart, so a provider that ignores the passed home defeats them.

**Caller isolation — a store serving a gateway serves several people.** When Hermes runs as a
gateway, one process handles many users, channels and workspaces. A single global store with no scope
columns will surface one person's memory inside another person's conversation. That is a privacy
failure, not a ranking bug, and no amount of recall tuning fixes it.

Every row carries a scope, and **every read and write is predicated on it**:

| Column | Holds |
|---|---|
| `agent_identity` | which agent the memory belongs to |
| `agent_workspace` | the working context it was formed in |
| `platform` | the surface it arrived through |
| `user_id` | stable identifier for the person, where one exists |
| `conversation_id` | optional narrower scope for group or tenant separation |

The default is the narrowest scope that fits the deployment: single-user CLI collapses to one scope
and costs nothing; a gateway must set them. **Sharing across scopes is explicit or it does not
happen** — there is no implicit widening, and a missing scope predicate is a bug, not a default.

A scope filter belongs in the SQL, not in post-filtering after ranking: a vector search that ranks
across everyone and then discards the wrong rows has already leaked them into the ordering, and will
return fewer results than asked for.

### 3.3 Stack (per the spec, friend-optimized)
- **Database — pluggable, SQLite default / MariaDB option.** A thin `store` interface with two
  backends:
  - **SQLite (default, zero-ops):** single file at `$HERMES_HOME/iconic/memory.db`. Vectors via the
    **`sqlite-vec`** extension when present; **graceful fallback** to an in-process NumPy cosine over
    the (bounded, pinned-in-RAM) active set when it isn't — friends install nothing.
  - **MariaDB (opt-in):** native `VECTOR` + `VEC_DISTANCE_COSINE`, for large corpora / multi-agent /
    power users. Same schema, same queries modulo the vector dialect.
  - Schema parity with Cowboy's `engram` (above). One `store.py` abstracts the dialect.
- **Embedder — embedded, no server.** **`fastembed` (ONNX) `bge-small-en-v1.5`** in-process on CPU
  (~130 MB, fast, deterministic). Optional: point at a llama.cpp embedding endpoint for those who
  already run one. `embed_model_id` + `embed_dim` stored per row so a model swap re-embeds cleanly.
- **Dreamer — CPU-pinned 2B Gemma.** **`gemma-2-2b-it` GGUF via llama.cpp**, **pinned to CPU + RAM**
  (`taskset`/`numactl --membind`, `n_gpu_layers=0`, `mmap`), so it never contends with the user's
  GPU chat models. Runs **detached/background** for extraction and during sleep. 2B is the floor that
  still extracts + adjudicates reliably; it's the friend-grade analog of Cowboy's 4B dreamer.

### 3.4 Flows (mapped to the real hooks)
- **Recall (live).** `on_turn_start` → `queue_prefetch(query)`: embed the user message, vector-search
  the active set, blend **0.6 cos + 0.25 sal + 0.15 rec**, dedup ≥ 0.97, **fail-open ≤ ~400 ms**,
  return a compact recall block. `system_prompt_block()` seeds the session with the top-K
  semantic/pinned facts, **char-bounded** to respect Hermes' frozen-snapshot + prefix cache.
- **Capture (auto).** `sync_turn` pushes each turn into the iconic ring (cheap). `on_session_end`
  and `on_delegation` **enqueue** an extraction job and return; a worker runs the dreamer and
  dedup-writes to episodic (see 3.4e). **No turn ever waits on the dreamer**, and no capture is lost
  if the process exits.
- **Active tools.** `iconic_remember(text, [layer], [pin])`, `iconic_recall(query)`,
  `iconic_archive(id)`, `iconic_restore(id)`, `iconic_forget(id)`, `iconic_pin(id)` via
  `get_tool_schemas`/`handle_tool_call`. Names are provider-owned: bare `remember` / `recall` /
  `forget` are broad enough to collide with another provider or a future core tool, and the losing
  side of a collision fails in ways that are hard to attribute. The skill can speak in the short
  conceptual verbs while calling these.
- **Sleep (maintenance).** `hermes iconic sleep` (run by cron or on idle): reinforce from the recall
  log → decay (ordering only) → **archive by last use, only when retention is enabled**
  (move-not-delete; see 3.4a) → consolidate episodic
  clusters [0.85, 0.97] → semantic via the dreamer → dreamer-judged promote/merge + conflict-detect
  → **self-check** (below).

### 3.4a Retention — what is kept is decided by last use, not age

A memory untouched for its layer's window is archived however old or new it is; one still being
recalled survives indefinitely. Last use falls back to creation, so a memory just written counts as
used. Working state gets weeks, durable knowledge months, pinned memories never expire. Salience and
decay only **order** search results; they do not decide what is kept.

This matters because an age-based floor retires memories that are still being used while keeping
recent ones nothing ever asks for. Keying on use means a memory earns its place, and the good ones
need no protection — they save themselves by being found.

**The law that makes it safe to switch on:** *never enable a rule that decides what is kept until
the signal it reads has actually been recorded.* If the last-use column has never been written — a
silently swallowed exception on the recall path is enough — every memory falls back to its creation
date and the entire store looks abandoned at once. Baseline the column first, then enable the rule.
The sleep job must refuse to archive an unusually large wave and report it instead of acting.

### 3.4b Self-check — the store inspects itself nightly

After the cognitive stages, a set of **deterministic** checks (no model call — the dreamer is small
and these are facts, not judgements) repairs what is mechanical and reports what needs a person:

- **Repairs:** transport markup that leaked into stored text, and memories carrying no usable
  vector — both re-embedded afterwards so the vector matches the text.
- **Reports:** memories past the embed cap, duplicate or missing update keys, a recall path that has
  never raised a salience, required columns no code writes, stale backups, the review backlog, and an
  unreachable embedder.

Findings are filed as **one dated memory per night**, episodic and unpinned, so the series ages out
on the ordinary fuse. That is safe because the checks are stateless: an unresolved finding is simply
re-measured and re-reported the next night. Nothing is remembered once.

### 3.4c The embed cap — the failure that leaves no trace

The embedder sees only the first *N* characters of summary + content (a `bge` model is a 512-token
model; a character cap is a rough proxy, and token-dense text such as hashes and paths packs far more
tokens per character, so the effective cap is lower still). **Text past the cap is stored and
readable but can never be matched by a search.** It raises no error and looks perfectly healthy.

Three consequences the plugin must build in:

1. **Warn at the point of writing.** `remember` returns the overflow it just created. A write that
   warns is not finished.
2. **Split at topic seams, never trim and never append.** Trimming deletes the specifics worth
   keeping; appending is worse, because one vector is a single average, so a bundle of topics matches
   nothing well. Skip splitting where the tail only restates the head — near-duplicate parts give the
   store several weakly-matching vectors instead of one that matches.
3. **Lead the summary with the subject.** The summary ranks and always survives truncation, so it
   must read like the query someone would later type, not like an abstract label.

### 3.4d Queues need a consumer

Promote, merge and conflict proposals are filed for judgement. If nothing ever reads a decision, they
accumulate for months while looking like diligence. Before shipping anything that files work for
later, decide what consumes it — and give every queued row a stable key derived from what it is
about, checked **before** the expensive model call rather than after. Rows keyed on columns left NULL
never collide, so a de-duplicating index silently does nothing and the same work is proposed again
every night.

### 3.4e Extraction is a durable queue, not a detached process

A lifecycle hook that spawns background inference and returns has put the only copy of its input in
RAM, in a process that is about to exit. Session end, delegation and compression are exactly the
moments the process is most likely to go away.

So the hook's job is to **persist the work, not to do it**:

1. Serialize a bounded extraction input to the store **before returning from the hook**.
2. Key the job by `(source_session, event_type, content_digest)` so the same input cannot enqueue
   twice.
3. Track state: `pending → leased → completed | failed`.
4. A worker leases, runs the dreamer, and writes results **idempotently** — replaying a completed job
   changes nothing.
5. Retry transient failures with bounded backoff; recover expired leases on startup, since a lease
   held by a dead process must not strand its job forever.
6. `on_session_switch()` flushes the outgoing session's ring; `shutdown()` checkpoints rather than
   abandons.

**`on_pre_compress` is the exception that must be synchronous.** Its whole purpose is to save what is
about to be dropped. Enqueuing and returning does not preserve anything if compression proceeds
immediately — the input is gone before the worker wakes. Whatever must survive compression is written
inside the hook, within its return contract; anything richer can be enqueued *in addition*.

### 3.4f Coexistence — Iconic is additive, not a replacement

An external provider runs **alongside** native memory. `MEMORY.md` and `USER.md` keep being written
and keep being injected at session start. Describing Iconic as "replacing" them invites a store that
silently disagrees with the block already in the prompt.

Give each a job, and say which wins:

| Layer | Owns | Authority |
|---|---|---|
| `USER.md` | stable identity and preferences that must always be present | authoritative for identity |
| `MEMORY.md` | compact environment facts, and how to recover the provider | authoritative for bootstrap |
| Iconic | the scalable corpus: episodic capture, semantic consolidation, tending | authoritative for everything it holds |

Native memory is **bounded and always injected**; Iconic is **unbounded and injected by relevance**.
That is the split — not "old versus new".

Mirroring native writes into Iconic is a decision to make explicitly, not to leave implicit. If
mirrored, each mirrored row carries provenance and a stable key so re-mirroring updates rather than
duplicates. If not mirrored, the two can disagree, and the recall block must not present an Iconic
fact as though it overrode the frozen native block. **Pick one and write it down.**

### 3.4g Archival and deletion are different operations

"Nothing is ever deleted" is the right promise for *retirement*. It is the wrong promise for a
secret that was captured by accident, personal data that must go, or a fact the user has asked to be
forgotten. Archival hides a row from recall; it does not remove it from the database, the exports, or
the backups.

Three distinct operations:

- **`archive(id)`** — reversible retirement. The row moves out of the active set, whole, and can come
  back.
- **`restore(id)`** — return an archived memory to active.
- **`forget(id)`** — authoritative removal. Not reversible, and it must reach everywhere the content
  went.

`forget` has to name its blast radius, or it is a false promise:

| Reaches | Because |
|---|---|
| the primary row | the obvious one |
| the vector index | an orphaned vector still matches and still ranks |
| consolidated descendants | a summary may carry the content forward verbatim |
| conflict and proposal records | these quote the text they were filed about |
| markdown exports | plain-text copies outlive the database |
| backups | state the retention window honestly rather than implying reach the design does not have |

A tombstone may record **that** a deletion happened, with a timestamp and scope, without keeping what
was deleted — enough for an audit trail, nothing more. Anything the design cannot actually purge
(existing backups, an export a user already copied) must be **stated as a limitation**, not quietly
omitted.

### 3.5 Config, CLI, ops
- `get_config_schema()`: **`retention.enabled` (default `false`)** and its per-layer idle windows,
  scope defaults (identity / workspace / platform / user), `db_backend` (sqlite|mariadb), `db_path`/DSN,
  `embedder` (fastembed|llama),
  `dreamer_model_path`, `cpu_affinity`, recall weights + budget, decay + cluster thresholds, iconic
  ring size, sleep schedule.
- `register_cli`: `hermes iconic sleep | stats | export | import | doctor | reembed | restore`.
  `sleep` takes `--dry-run` and `--reinforce-only`, so instrumentation can be proven without running
  a stage that archives.
- **Backup:** round-trippable **markdown export/import** (Cowboy's pattern) — friends can read, edit,
  and version their memory in plain text.
- **Failure posture:** `is_available()` does no network; missing dreamer/embedder degrades to
  store-only (manual `remember` + keyword recall) rather than failing; recall always fail-opens;
  dreamer crashes are logged and skipped, never block.

### 3.6 What this fixes vs. native Hermes memory
Live semantic recall (was: frozen snapshot) · auto-extraction (was: manual-only) · unbounded
self-tending corpus with decay/consolidation (was: ~1,300-token hand-edited notebook) · subagent +
pre-compaction capture (was: none) · CLI maintenance + plain-text backup (was: none).

---

## 4. The bundled skill — `winnow-SKILL.md`

The plugin ships **`winnow-SKILL.md`** and the installer copies it into the agent's skills
directory. It is not optional decoration: a store degrades quietly without it, and the failure is
invisible — no errors, just an answer that is present and unreachable.

Winnow covers three things the engine cannot enforce on its own:

- **Planting** — choosing the layer so dated work can age out, writing a summary that reads like the
  query someone would later type, measuring against the embed cap instead of estimating, keying a
  memory so it can be updated rather than duplicated, and splitting at topic seams when it will not
  fit.
- **Winnowing** — retention by last use, triaging before splitting, erring toward keeping when
  judging what to retire, and never leaving two memories that both claim to be current.
- **Repairing at scale** — the guards a bulk rewrite needs: never delete in a fixer, do not identify
  records by a pattern ordinary text can satisfy, verify a structural finding before acting on it,
  and measure length before and after.

**Hermes tool mapping.** Winnow is written against a generic store; in this plugin the calls are
`recall(query)`, `remember(text, [layer], [pin])`, `forget(id)` and `pin(id)`. Two habits are worth
stating in the agent's own terms:

- **Recall before you reconstruct.** The store is the memory; the context window is a lossy cache
  that can surface a stale entry. When the two disagree, the store wins unless you have just
  verified otherwise.
- **Let auto-capture do the bulk.** The dreamer extracts durable facts at session end. Reserve
  `remember` for the durable and non-obvious, and never codify a guess — a wrong memory outlives the
  session and pollutes every later recall.

## 5. Open decisions (my recommendation first)
1. **SQLite vector path:** ship `sqlite-vec`-when-present + NumPy-cosine fallback (**recommended** —
   zero friend install) vs. require `sqlite-vec`. 
2. **Embedder:** `fastembed` ONNX in-process (**recommended**, no server) vs. a llama.cpp embed
   server (matches Cowboy but adds a process).
3. **Dreamer cadence:** `on_session_end` extraction + cron/idle `sleep` (**recommended**) vs. also a
   mid-session periodic extract (more captures, more CPU).
4. **Scope of v1:** recall + auto-capture + tools + sleep-core (**recommended**) vs. also conflict-
   detect + judged-merge in v1 (closer to Cowboy parity, more dreamer logic).

## 6. Phasing
- **v1 (MVP, friend-usable):** store (SQLite default) + fastembed recall + `prefetch`/
  `system_prompt_block` + `sync_turn`/`on_session_end` dreamer extract + the four tools + `hermes
  iconic sleep` (decay/archive/consolidate) + markdown backup + the skill.
- **v2:** MariaDB backend + judged promote/merge + conflict-detect + `on_delegation`/`on_pre_compress`
  capture + `doctor`/`reembed` CLI.
