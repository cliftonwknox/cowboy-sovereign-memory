# Hermes Iconic Memory — v2.1

**Real, self-managing memory for [Hermes Agent](https://github.com/NousResearch/hermes-agent) —
local, private, drop-in.**

> **v2.1 — the integration and lifecycle pass.** v2.0 corrected the *memory model*: what a store
> keeps is decided by **last use, not age**, guarded by the law that you never enable a rule deciding
> what is kept until the signal it reads has actually been recorded. v2.1 corrects the parts that
> decide whether it is safe to *install*: **profile and per-user isolation**, the real provider
> discovery path and activation, **retention off until proven**, a **durable extraction queue**,
> **coexistence** with native memory instead of replacing it, and **deletion** separated from
> archival. The care discipline ships as **`winnow-SKILL.md`**. See `CHANGELOG.md`.

Hermes' built-in memory is a pair of small text files (~1,300 tokens) the agent hand-edits and that
are frozen into the prompt at session start. Iconic Memory runs alongside them and adds a memory that
**remembers on its own**, **recalls by meaning**, and **tends itself** — all on your machine, with a
single database file and no GPU required.

- 🧠 **Auto-capture** — a small local model reads each session and extracts the durable facts.
- 🔎 **Semantic recall** — every turn it surfaces what's *relevant*, instead of one frozen block.
- 🌙 **Self-tending** — what nothing asks for retires, related memories merge, important ones persist.
  Retirement **archives** (reversible); deleting for real is a separate, explicit operation.
- 🔌 **Drop-in** — a standard Hermes `MemoryProvider` plugin. No fork; remove it and native memory is
  untouched.
- 🏠 **Local & private** — your data stays in your own DB; nothing leaves the machine.
- 🪶 **Zero-ops default** — SQLite + an in-process embedder. A friend installs it and goes.

---

## The documents (read in this order)

| # | Document | For | Read it to… |
|---|---|---|---|
| 1 | **`hermes-iconic-memory-overview.md`** | Anyone deciding | Understand what it is, its components, benefits, the phased plan, and dependencies. **Start here.** |
| 2 | **`hermes-iconic-memory-design.md`** | The builder | Build it: the architecture, the exact Hermes plug-in hook mapping, the data model, the bundled skill, and the open decisions. |
| 3 | **`hermes-iconic-memory-install-runbook.md`** | The *installing agent* | Install it on a real machine: a preflight hardware check, an honest go/no-go briefing, then a verify-every-step recipe. |
| 4 | **`winnow-SKILL.md`** | The *running agent* | Use the store well: writing memories that can be found again, clearing away what has finished, and repairing many at once without losing anything. **Installed, not just read.** |

> Deciding whether it fits your machine? → **Overview §3 (benefits)** + **Runbook Phase 1 (the fit
> table)**. Building it? → **Design**. Installing it? → hand the **Runbook** to your agent.

---

## How it works (one diagram)

```
            ┌─────────────────────────────────────────────┐
  you ⇄ Hermes Agent                                        │
            │   ▲ recall (every turn, ~ms, fail-open)       │
            ▼   │                                           │
   ┌────────────────────────┐     extract (background, never blocks)
   │  Iconic Memory plugin   │ ───────────────►  ┌──────────────────┐
   │  • recall engine        │                   │ Dreamer: 2B Gemma │
   │  • memory tools         │ ◄───────────────  │ CPU-pinned, off-  │
   │  • sleep/maintenance    │   consolidate     │ GPU, detached     │
   └───────────┬─────────────┘                   └──────────────────┘
               │ embed (in-process bge-small, ONNX, CPU)
               ▼
   ┌─────────────────────────────────────────────┐
   │  Store:  Iconic (RAM) → Episodic → Semantic   │
   │  SQLite (default)  |  MariaDB (option)         │
   └─────────────────────────────────────────────┘
```

**Recall is on the hot path and cheap; the dreamer is the only heavy part and it runs in the
background** — so the agent stays responsive even on modest hardware, and weak machines can run
**recall-only mode** (full semantic recall + manual `remember`, no auto-extractor).

---

## Quick fit check

| | 🟢 Full mode | 🟡 Works (dreamer lags, in background) | 🔴 Recall-only mode |
|---|---|---|---|
| RAM | ≥ 8 GB (≥4 free) | 6–8 GB | < 4 GB |
| CPU | ≥ 4 modern cores | 2 cores | single old core / mobile |

The runbook's preflight detects this automatically and tells you which mode fits — in one screen,
no lecture.

## Dependencies at a glance

- **Host:** Hermes Agent + Python 3.11+.
- **Core:** `fastembed` (+ onnxruntime), `numpy`, SQLite (stdlib); optional `sqlite-vec`.
- **Full mode (dreamer):** Ollama (`ollama pull gemma2:2b`) *or* `llama-cpp-python` + a
  `gemma-2-2b-it` Q4_K_M GGUF (~1.7 GB) + a few CPU cores and ~3–4 GB free RAM.
- **Power option:** MariaDB 11.7+ (native `VECTOR`) + a Python connector.
- **None required:** no cloud, no API keys, no GPU.

---

## Status

Design, not an installation guide. The memory model is grounded in a running engine; the Hermes
integration points are read from source, but nothing here has been built or installed yet. The
install commands are POSIX/Linux; the preflight's macOS and Windows paths are best-effort and
unverified. Build order in Design §6.

*Built by Cowboy Claude with Clifton Knox.*
