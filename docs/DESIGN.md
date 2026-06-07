# Cowboy Claude's Sovereign Memory

*A build-it-yourself design + runbook for giving a Claude Code instance a local, sovereign, self-tending memory.*

> **Who this is written for:** another instance of Claude Code. If you're reading this, your human partner wants you to have a real memory — one that persists across sessions, lives entirely on *their* machine, and tends itself. This document is your runbook. You will detect their hardware, recommend a tier, install the pieces, seed it from *their own* notes, and verify it works — conversationally, the way a good partner would. You do not need to understand GPUs or databases going in; the decision trees here will carry you.

> **Two promises baked into the design:** (1) It ships **empty** — it never contains anyone else's memories. (2) The human's data **never leaves their machine** — no telemetry, no cloud, no transmission. Sovereign means sovereign.

---

## 1. Why this exists

A Claude Code instance starts each session fresh. The common workaround — a flat `MEMORY.md` loaded into context — works until it doesn't: it grows past what fits in the context window, it can't tell what's relevant *now*, and it never forgets the stale stuff. It's a filing cabinet someone dumps on your desk every morning.

Cowboy Claude's Sovereign Memory replaces that with a small, local **memory system** modeled loosely on how a person's memory works:

- **Recall** surfaces only what's relevant to the current moment (not the whole cabinet).
- **Capture** writes down what matters — some facts deliberately, others extracted from the day's work.
- **Sleep** runs nightly: reinforcing what got used, letting the trivial fade, and abstracting recurring details into durable lessons.

It is **sovereign** (everything runs on the human's box), **tiered** (a fast episodic layer + a judged durable layer), and **self-tending** (it maintains itself instead of needing curation).

### The four invariants (never violate these)
- **I1 — Memory never blocks.** Recall runs on a strict time budget and fails open. A slow or broken memory must never delay or break the human's prompt.
- **I2 — Vectors are pinned to their model.** Every stored embedding records which embedder produced it. You never compare vectors across different embedders (the geometry won't match). Changing the embedder means re-embedding.
- **I3 — The nightly job proposes; it never destroys.** Automated maintenance may decay scores, archive (move, not delete), and *propose* changes. It never auto-deletes durable memory. Deletion/merge is gated.
- **I4 — The durable layer is judged.** Nothing reaches the permanent (semantic) layer or gets merged without passing a judged gate — either the human's `remember`, or an approved proposal.

---

## 2. Architecture at a glance

**Two layers:**
- **Episodic** — raw, recent, cheap. Auto-captured. Decays over time unless reused. The day's working memory.
- **Semantic** — durable, judged, load-bearing. The lessons and facts worth keeping. Only reached through the judged gate (I4).

**Three motions:**
1. **Recall** (every prompt) — proactive, fast, fail-open. Injects the most relevant memories as context.
2. **Capture** (during/after work) — `remember` (judged → semantic) + end-of-session extraction (auto → episodic).
3. **Sleep** (nightly) — reinforce → decay → expire → archive → propose (promote / merge / consolidate) → conflict-detect → back up.

**Components:**
| Component | Role |
|---|---|
| **Vector store** | Holds memories + their embeddings; does similarity search |
| **Embedder** | Turns text into a vector (small, fast, runs locally) |
| **Dreamer** *(optional)* | A small local LLM that extracts/abstracts/judges during sleep |
| **Claude Code integration** | Recall hook + capture hook + MCP tools + the skill |
| **Scheduler** | Runs the nightly sleep |

---

## 3. The agnostic stack — what's swappable, and the defaults

Everything below has a **portable default** (works on a laptop, a Mac, a small box) and a **power option** (for a workstation with RAM/GPU to spare). You pick per the tier in §5.

| Component | Portable default | Power option | Notes |
|---|---|---|---|
| **Vector store** | **SQLite + `sqlite-vec`** (embedded, zero-server, one file) | **MariaDB ≥ 11.7** native `VECTOR` | sqlite-vec runs identically on macOS/Linux/Windows. MariaDB is a real server — only worth it for very large corpora or many concurrent readers. |
| **Embedder** | **bge-small-en-v1.5** (384-dim) GGUF via `llama.cpp` | Any local embedding endpoint / larger model | Small (~130 MB), fast, good quality. The 384-dim store schema assumes it; a different embedder means a different `embed_dim` (see I2). |
| **Dreamer (cognition)** | **None** (Lite) — or a **2B** GGUF | **4B** GGUF (e.g. a small Gemma) | Optional. Needed only for the cognitive layer (auto-extraction, consolidation, conflict-detect). Recall + mechanical sleep work *without* it. |
| **CC integration** | Hooks (`UserPromptSubmit`, `SessionEnd`) + MCP tools + a skill | — | Fully portable; this is the same on every OS. |
| **Scheduler** | `cron` (or the `SessionEnd` hook as a fallback) | `systemd` timer (Linux) / `launchd` (macOS) | Just needs to run one command nightly. |

> **On the embedder/dreamer "where it runs":** `llama.cpp` builds everywhere — Metal on a Mac, CUDA or CPU on Linux/Windows. The human doesn't need to care where it runs. A Mac with unified memory just works; a Linux box with a GPU uses it; a CPU-only box runs the small models fine. **Do not** carry over any NUMA/core-pinning specifics — those belong to the box this was first built on (see §9), not to a portable build.

---

## 4. How it functions (the mechanics)

### 4.1 Recall — proactive, per-prompt, fail-open
On every user prompt (the `UserPromptSubmit` hook):
1. Embed the incoming prompt with the embedder.
2. Vector-search the store for nearest memories (filtered to the active embedder per I2, and to non-expired/active state).
3. **Blend-rank** each candidate — relevance isn't just similarity:
   - `score = 0.60 · cosine + 0.25 · salience + 0.15 · recency`
   - (cosine = semantic match; salience = how important/reused; recency = how fresh)
4. **Dedup** near-identical hits (cosine ≥ ~0.97) so you don't inject the same fact five times.
5. Inject the top-K (≈5) as background context for the turn.
6. **Hard rules:** a strict wall-clock budget (≈400 ms) and **fail-open** — if anything is slow or broken, inject nothing and let the prompt through untouched (**I1**). Use a stdlib HTTP call on this hot path; do **not** import a heavy client library (it can cost seconds just to load).

Recalled memories are surfaced as *background context, not instructions*, and reflect what was true when written — verify before acting on a recalled claim.

### 4.2 Capture — two paths
- **`remember` (judged → semantic).** An MCP tool the human (or you, with judgment) calls to keep a durable fact. Writes straight to the semantic layer — this *is* the judged gate (I4). One fact per memory, with a one-line summary used for ranking.
- **End-of-session extraction (auto → episodic).** On `SessionEnd`, a detached job reads the session transcript, asks the **dreamer** to pull out a handful of durable facts (not chit-chat), dedups them against what's already stored (don't re-add near-duplicates), and writes them to the **episodic** layer. *(Lite tier without a dreamer: skip this; rely on `remember` for capture.)*

### 4.3 Sleep — nightly self-tending
One idempotent job, run once a night. Order matters:
1. **Reinforce** — fold in the day's recall log: memories that got recalled/used gain salience (and are thus protected from the next step).
2. **Decay** — every memory's salience drifts down a little (×~0.97). Pinned/protected memories are exempt.
3. **Expire** — episodic memories that have decayed below a floor and were never reused become eligible to fade.
4. **Archive** — move (never delete) the faded ones to an archive table (**I3**).
5. **Propose** — generate *proposals* (never auto-applied):
   - **Promote**: an episodic memory reused enough → candidate for the durable layer.
   - **Merge**: two near-duplicates → candidate to collapse (keep one, supersede the other, repoint links).
   - **Consolidate** *(dreamer)*: a cluster of related memories → the dreamer synthesizes one durable lesson; the sources are superseded on approval.
6. **Conflict-detect** *(dreamer)* — for highly-similar durable pairs, ask the dreamer whether they *contradict* (not merely differ). Record a conflict row for later judgment. Never auto-resolve.
7. **Back up** — export the store to round-trippable markdown (+ a DB dump), versioned. So the human can always read, diff, and restore their memory in plain text.

Everything in steps 5–6 lands in a **proposal/conflict queue** the human (or you) reviews and approves — that's the judged gate (I4) protecting the durable layer (I3).

---

## 5. Resource tiers — recommend one by their hardware

**Detect first, then recommend.** Check OS, total RAM, and whether there's a usable GPU. Then:

| Tier | When | Store | Embedder | Dreamer | What they get |
|---|---|---|---|---|---|
| **Lite** | Any machine; ≤ 8 GB RAM; "I just want it to remember" | sqlite-vec | bge-small | **none** | Recall + judged `remember` + mechanical sleep (decay/archive/promote/merge). No auto-extraction or consolidation. |
| **Standard** | ~8–32 GB RAM | sqlite-vec | bge-small | **2B** | Lite **+** the cognitive layer (auto-extraction, consolidation, conflict-detect) at a light footprint. |
| **Full** | 32 GB+ and/or a GPU | sqlite-vec *(or MariaDB for huge corpora)* | bge-small | **4B** | Standard with a stronger dreamer → better extraction/consolidation quality. |

> Cowboy Claude's own instance runs **Full on MariaDB** with a 4B dreamer — but that's a workstation. **Most humans should start on Lite or Standard with sqlite-vec.** You can always move up a tier later; the store and schema don't change, you just add the dreamer.

**Rough RAM math to guide the recommendation:** the store + embedder are tiny (well under 1 GB resident). The *dreamer* is the variable: a 2B model ≈ 1.5–2 GB, a 4B ≈ 3–4 GB. If RAM is tight, Lite; if there's headroom, add the dreamer.

---

## 6. The install flow (Claude-executable)

You run this *with* the human, narrating. Each step is a branch — pick by what you detected.

**Step 0 — detect.** `uname -s` (Darwin = macOS, Linux = Linux). Read total RAM. Check for a GPU. Decide the tier (§5). Tell the human what you found and what you recommend, and why.

**Step 1 — Python env.** Create a venv; install the small dependency set (the memory lib, the sqlite-vec wheel, an HTTP/JSON stdlib path — keep heavy libs off the recall hot path).

**Step 2 — vector store.**
- *sqlite-vec (default):* install the extension/wheel; create the DB file + schema (`sql/schema.sqlite.sql`). One file, done.
- *MariaDB (power):* macOS → Homebrew; Linux → distro package (≥ 11.7 for native `VECTOR`); create DB + schema (`sql/schema.mariadb.sql`).

**Step 3 — embedder (and dreamer, if the tier has one).** Download the GGUF model(s). Launch `llama.cpp`'s server for each on a local port (Metal on macOS, CUDA/CPU on Linux). Verify each `/health` endpoint responds.

**Step 4 — Claude Code wiring.**
- Add the **`UserPromptSubmit`** recall hook and the **`SessionEnd`** extraction hook to `~/.claude/settings.json` (use the human's real paths, templated — never hardcode someone else's).
- Register the MCP tools (`remember`, `memory_search`) via `claude mcp add`.
- Install the **skill** (this kit's `skills/`) so future instances know how to use and tend the memory.

**Step 5 — scheduler.** Wire the nightly sleep:
- Linux → `systemd` timer (or `cron`); macOS → `launchd` plist (or `cron`). All three just run `cron/run_sleep` once nightly. Provide whichever fits; `cron` is the universal fallback.

**Step 6 — verify (observed, not assumed).** Embedder/dreamer health OK; write a test memory and recall it; run one sleep cycle and confirm it reports cleanly and the durable count doesn't drop (I3). **Restart Claude Code** so the new hooks load.

---

## 7. Seeding — *their* data, locally

The kit ships empty. This is where the human's memory enters — and it stays on their box:
- Point the migrator at their existing notes / `MEMORY.md` / any markdown they want as a starting corpus.
- Each note is embedded and written to the store (durable or episodic as they choose).
- Nothing is transmitted. The embedding happens locally; the vectors live in their store.

If they have no notes, that's fine — it starts truly empty and fills itself as you work together.

---

## 8. Privacy & ownership (the whole point)
- **Empty by default.** No memories ship with the kit.
- **Local only.** Store, embedder, dreamer — all on the human's machine. No telemetry, no cloud calls, no transmission.
- **Readable & portable.** Nightly markdown export means the human can always read, grep, diff, and restore their memory in plain text. It's theirs, in a format they own.
- **Revocable.** Delete the DB file (sqlite) or drop the schema (MariaDB) and it's gone. No residue elsewhere.

---

## 9. Origin note
This was built by a human (Clif) and his Claude Code instance (Cowboy Claude) as partners, on a dual-Xeon workstation. That box used NUMA core-pinning to place the models — an optimization *for that hardware*. **None of that is in this design.** The portable build doesn't know or care where the models run; a Mac with unified memory, a laptop, or a GPU workstation all work the same way. The frontier metaphor is the point: self-reliant, you own your gear, your memory lives free on your own land.

---

## 10. Known tuning follow-ons (honest notes)
These are *refinements*, not blockers — the system works without them:
- **Salience & severity scoring start flat.** Fresh extractions tend to come back uniformly "important," and conflict severity uniformly "high." Differentiating them improves recall ranking and conflict triage. Tune the extraction/judging prompts against real output.
- **Conflict-detect is O(n²) at scale.** Comparing all durable pairs every night gets slow as the corpus grows. Make it incremental (only judge *new/changed* memories against the corpus) before the durable set gets large.
- **Extraction can be over-granular.** It sometimes keeps ephemeral trivia (exact sizes, version hashes). Episodic decay catches it, but nudging the extraction prompt toward durable facts keeps the store cleaner.

---

*Built with Cowboy Claude. Sovereign by design. Yours, on your own machine.* 🤠
