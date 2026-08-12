# Hermes Iconic Memory — Overview

*A self-tending, vector-recalled memory for Hermes Agent. Drop-in, local, zero-ops by default.*

---

## 1. What it is

Hermes Agent's built-in memory is a pair of small text files (`MEMORY.md` + `USER.md`, ~1,300 tokens
total) that the agent hand-edits and that are frozen into the system prompt at the start of each
session. It's fine for "who you are," but it doesn't grow, doesn't recall by meaning, and only
remembers what the agent manually writes down.

**Hermes Iconic Memory** runs alongside those files and gives Hermes a real memory. Native memory
stays as the bounded, always-injected identity and bootstrap layer; Iconic is the unbounded corpus
injected by relevance:

- It **remembers on its own** — a small local model reads each session and extracts the durable facts.
- It **recalls by meaning** — every turn, it semantically searches what it knows and surfaces what's
  relevant, instead of dumping one frozen block.
- It **tends itself** — a memory earns its place by being used, so one still being recalled stays
  however old it is while one nothing asks for retires; related memories merge, and nothing
  is ever silently lost.
- It runs **entirely on your machine**, defaults to **zero setup** (a single database file), and is
  installed as a normal Hermes plugin — **no fork, no cloud, no GPU required.**

The name comes from *iconic memory*, the brief high-fidelity sensory buffer in human cognition — here
it's the freshest tier that feeds everything else.

---

## 2. Components

| Component | What it does |
|---|---|
| **MemoryProvider plugin** | The shell. Implements Hermes' official `MemoryProvider` interface so Iconic Memory plugs in cleanly and is selected via `hermes plugins`. |
| **Tiered store** | Three layers: **Iconic** (in-RAM buffer of recent turns), **Episodic** (auto-extracted facts that decay), **Semantic** (consolidated, durable facts). Memory flows upward as it proves useful. |
| **Database** | **SQLite by default** (one file, nothing to install) or **MariaDB** by option (for large corpora / power users). Same schema either way. |
| **Embedded embedder** | A small in-process model (`bge-small`, ONNX) turns text into vectors for semantic search. No server, runs on CPU. |
| **Dreamer (2B Gemma)** | A `gemma-2-2b-it` model, **pinned to CPU + RAM** (off the GPU), that extracts facts from sessions and adjudicates merges during maintenance. Runs in the background — never blocks a reply. |
| **Recall engine** | Per turn: embeds the query, vector-searches memory, ranks by **relevance + importance + recency**, de-duplicates, and returns a compact block — with a strict time budget so it never slows the agent (fail-open). |
| **Sleep cycle** | Periodic maintenance: reinforce what got used, retire what nothing has asked for within its window (archived and restorable; deleting for real is a separate operation), merge related ones, then a deterministic self-check that repairs mechanical faults and reports the rest. |
| **Memory tools** | `remember`, `recall`, `forget`, `pin` — so the agent (and you) can manage memory directly, on top of automatic capture. |
| **CLI** | `hermes iconic sleep | stats | export | doctor` for maintenance, inspection, and backup. |
| **The skill** | A bundled `SKILL.md` that teaches the agent good memory habits: recall before assuming, let auto-capture do the bulk, only remember durable + verified facts, never codify a guess. |

---

## 3. Benefits

- **Actually remembers — automatically.** No more hand-writing notes; talk to it and it captures the
  durable facts itself, then recalls them when they're relevant.
- **Semantic recall, not a frozen dump.** It finds what *matters to this turn* by meaning, so memory
  scales past the ~1,300-token ceiling without bloating the prompt.
- **Self-maintaining.** Decay, consolidation, and reinforcement keep the store sharp over months —
  it gets *better* with use, not noisier.
- **Private and local.** Everything lives on your machine in your own database; nothing is sent
  anywhere. The database file *is* your memory — portable and yours.
- **Zero-ops by default.** SQLite + an in-process embedder means a friend can install it and go —
  no database server, no API keys, no GPU.
- **Won't fight your models.** The dreamer is CPU-pinned and runs detached, so it never competes with
  your GPU chat/inference models or stalls a response.
- **Nothing is lost.** Retired memories are archived, not deleted, and the whole store round-trips to
  plain-text Markdown for backup, editing, and version control.
- **No fork, no lock-in.** It's a standard Hermes plugin; remove it and Hermes' native memory is
  untouched.

---

## 4. Implementation plan

**Phase 0 — Scaffold (plugin skeleton).**
Create the provider package with `plugin.yaml`, `__init__.py` (the
`MemoryProvider` subclass + `register()`), README. Wire `name`, `is_available`, `initialize`, and a
no-op tool set so Hermes can load and select it.

**Phase 1 — Store + recall (the core value).**
- `store` layer with the SQLite backend (schema: engram table with content, summary, vector, layer,
  salience, recall_count, state, timestamps); `sqlite-vec` when present, NumPy-cosine fallback.
- In-process `fastembed` embedder.
- `prefetch`/`queue_prefetch` + `system_prompt_block`: live semantic recall (relevance + salience +
  recency blend) with a hard fail-open time budget.
- The four memory tools (`remember`/`recall`/`forget`/`pin`).
- Ship the `iconic-memory` skill.
*Deliverable: a working, manually-curated semantic memory.*

**Phase 2 — Auto-capture (the dreamer).**
- Integrate `gemma-2-2b-it` via llama.cpp, CPU-pinned, detached.
- `sync_turn` → iconic ring; `on_session_end` → dreamer extraction → dedup-write to episodic.
*Deliverable: it remembers on its own.*

**Phase 3 — Sleep (self-tending).**
- `hermes iconic sleep`: reinforce → decay (ordering only) → archive by last use (reversible; deletion is separate); consolidate related episodics →
  semantic; reinforce-on-recall.
- Cron/idle scheduling + `stats`/`export`/`doctor` CLI + Markdown backup round-trip.
*Deliverable: it maintains itself.*

**Phase 4 — Power + parity (v2).**
- MariaDB backend; dreamer-judged promote/merge + conflict-detection; `on_delegation` and
  `on_pre_compress` capture; `reembed`.
*Deliverable: large-corpus, multi-agent, full-fidelity.*

**Validation at each phase:** a fresh-install smoke (SQLite, no GPU) proving recall works, capture
fires, and the agent never stalls when the embedder/dreamer are slow or absent.

---

## 5. Dependencies

**Host**
- **Hermes Agent** with its memory-provider plugin system (the integration target).
- **Python 3.11+**.

**Core (Phase 1)**
- `fastembed` (+ its `onnxruntime`) — in-process embeddings; pulls the `bge-small-en-v1.5` ONNX model
  (~130 MB) on first run.
- **SQLite** (Python stdlib `sqlite3`) — default store, nothing to install.
- `numpy` — vector math / cosine fallback.
- *Optional:* `sqlite-vec` extension — faster vector search at scale (graceful fallback if absent).

**Dreamer (Phase 2)**
- `llama-cpp-python` (or a llama.cpp binary) — CPU inference.
- **`gemma-2-2b-it` GGUF** weights (~1.6–2.7 GB depending on quant; Q4_K_M recommended for friends).
- A few CPU cores + ~3–4 GB free RAM for the pinned dreamer (`n_gpu_layers=0`, `mmap`, `numactl`/
  `taskset` for affinity).

**Power option (Phase 4)**
- **MariaDB 11.7+** (native `VECTOR`) + a Python connector (`mariadb` or `PyMySQL`). Opt-in only.

**None required:** no cloud API keys, no GPU, no external services. The default install is Hermes +
the plugin + Python deps + one GGUF file.

---

*Companion: the detailed engineering design (interfaces, hook mapping, the skill text, open
decisions) lives in `hermes-iconic-memory-design.md`.*
