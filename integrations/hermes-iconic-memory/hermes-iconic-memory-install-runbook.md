# Hermes Iconic Memory — Install Runbook (for an installing agent)

**Audience: the LLM agent performing the install.** You are setting up Hermes Iconic Memory on a
human's machine. Work the phases **in order**. The bar (per install discipline): the human ends with
a **verified, working** memory plugin — or a **clear, friendly** reason their hardware isn't a fit and
what they can run instead. Never skip a verification. Never guess past a failure — stop and report.

> **Tone rule — do not be a pill.** The upfront briefing (Phase 2) must be **short, warm, and
> honest**: what it needs, how their machine looks, what gets downloaded, one clear go/no-go read,
> then a single question. No wall of warnings, no doom. One screen, then let them decide.

---

## Phase 0 — Orient (silent; you, the agent)

Confirm the ground truth before touching anything:
- Hermes is installed: `hermes --version` (if missing → tell the human Iconic Memory is a Hermes
  plugin and stop until Hermes is installed).
- You can run shell commands on this host and write to the Hermes home (`$HERMES_HOME`, default `~/.hermes/`).
- You have the Iconic Memory plugin source (a repo URL or a local package dir — `<ICONIC_SOURCE>`).

---

## Phase 1 — Preflight (read-only inspection)

Run these and record the numbers. Pick the right command for the OS.

| Check | Linux | macOS | Windows (PowerShell) |
|---|---|---|---|
| Total RAM (GB) | `awk '/Mem:/{printf "%.1f\n",$2/1024}' <(free -m)` | `echo "scale=1;$(sysctl -n hw.memsize)/1073741824" \| bc` | `[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)` |
| Free RAM (GB) | `awk '/Mem:/{printf "%.1f\n",$7/1024}' <(free -m)` | `vm_stat \| awk '/free\|inactive/{s+=$NF}END{printf "%.1f\n",s*4096/1073741824}'` | `[math]::Round((Get-Counter '\Memory\Available MBytes').CounterSamples.CookedValue/1024,1)` |
| CPU logical cores | `nproc` | `sysctl -n hw.logicalcpu` | `(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors` |
| CPU model | `grep -m1 'model name' /proc/cpuinfo` | `sysctl -n machdep.cpu.brand_string` | `(Get-CimInstance Win32_Processor).Name` |
| Free disk (GB) | `df -BG --output=avail . \| tail -1` | `df -g . \| tail -1` | `(Get-PSDrive C).Free/1GB` |
| Python | `python3 --version` | `python3 --version` | `py --version` |

> **Agent note:** the Linux column is verified; the macOS/Windows free-RAM parses are best-effort.
> If any value comes back empty or implausible, don't trust the parse — show the human the raw
> `free` / `vm_stat` / Task-Manager readout and reason from that. A wrong number here drives a wrong
> go/no-go.

**Fit thresholds (assess against the recorded numbers):**

| Resource | 🟢 Good | 🟡 Marginal | 🔴 No-go for full mode |
|---|---|---|---|
| Total RAM | ≥ 8 GB | 6–8 GB | < 4 GB |
| Free RAM (at install time) | ≥ 4 GB | 2.5–4 GB | < 2.5 GB |
| CPU | ≥ 4 modern cores (≥2 GHz x86-64, Apple Silicon, or recent ARM) | 2 cores | single old core / low-power mobile |
| Free disk | ≥ 3 GB | 2–3 GB | < 2 GB |
| Python | 3.11+ | 3.11+ | < 3.11 |

**What "marginal/no-go" actually means (use this to brief honestly, not to scare):**
- **Recall runs every turn and is cheap** (a tiny embedder, ~milliseconds) — it stays fast even on
  weak hardware. The agent never stalls waiting on memory (recall is fail-open with a hard time
  budget).
- **Only the 2B "dreamer" is heavy**, and it runs **detached in the background** (after a session,
  and during maintenance). On a 🟡 CPU it still works — memories just take longer to appear after a
  chat. On a 🔴 CPU it may be too slow or not fit in RAM.
- **There is a graceful fallback: "recall-only mode"** (no dreamer). You get full semantic recall +
  manual `remember`, just no automatic extraction. **A weak/old machine is not excluded — it runs
  recall-only.** Recommend this when RAM/CPU is 🔴.

**Downloads the install will pull (state these to the human up front):**
- Python deps (fastembed/onnxruntime, numpy, the plugin) — tens of MB.
- The embedder model `bge-small-en-v1.5` (ONNX) — **~130 MB**, fetched on first use.
- Full mode only: the dreamer model `gemma-2-2b-it` (Q4_K_M GGUF) — **~1.7 GB**.

---

## Phase 2 — Briefing + GO/NO-GO gate (present to the human; then WAIT)

Fill this template from Phase 1 and show it. Keep it to one screen. Warm, plain, honest:

```
Iconic Memory gives Hermes real, self-managing memory — it remembers across sessions on its
own and recalls by meaning. It runs entirely on your machine. Here's the quick check:

  Your machine:  <RAM> GB RAM (<FREE> free) · <CORES> cores · <CPU model> · <DISK> GB free
  My read:       <🟢 Good fit — full mode | 🟡 Works, with a note | 🔴 Recommend recall-only mode>
  <one-line reason, e.g. "plenty of headroom" / "the background extractor will be a bit slow,
   but it never slows your chats" / "not enough free RAM for the 2B model, so I'd skip the
   auto-extractor and run recall-only — still fully useful">

  Will download:  ~130 MB embedder<, and ~1.7 GB for the 2B dreamer model> (one time)
  Footprint:      one local database file in $HERMES_HOME/iconic/ — nothing leaves your machine

Want me to go ahead with <full mode | recall-only mode>?  (yes / no / tell me more)
```

- If the human says **no** → stop cleanly, no changes.
- If **tell me more** → answer briefly, then re-ask.
- If **yes** → proceed to Phase 3 with the agreed mode. **Record the chosen mode.**

---

## Phase 3 — Install (only after an explicit "yes"; verify every step)

Each step: run the command, **check the expected result, and only then continue.** If a result
doesn't match, stop and report it to the human verbatim.

### 3.1 Python environment + core deps
```
python3 -m venv $HERMES_HOME/iconic/venv
$HERMES_HOME/iconic/venv/bin/pip install -U pip
$HERMES_HOME/iconic/venv/bin/pip install fastembed numpy hermes-iconic-memory   # or: pip install <ICONIC_SOURCE>
```
**Verify:** `$HERMES_HOME/iconic/venv/bin/python -c "import fastembed, numpy, hermes_iconic_memory; print('ok')"` → prints `ok`.

### 3.2 Embedder warm-up (pre-fetch so first recall isn't slow)
```
$HERMES_HOME/iconic/venv/bin/python -m hermes_iconic_memory.warm_embedder
```
**Verify:** prints the model id + embedding dim (e.g. `bge-small-en-v1.5 dim=384`) and exits 0. (This
is the ~130 MB download.)

### 3.3 Dreamer model — **full mode only** (skip entirely for recall-only)
Choose the path you'll record in config:

**Path A — Ollama (recommended for friends; handles the download, license, and CPU serving):**
```
# install ollama if absent: https://ollama.com/download
ollama pull gemma2:2b
```
**Verify:** `ollama list | grep gemma2:2b` shows the model. CPU-pin it in config (3.5) via the ollama
endpoint + `num_gpu: 0`.

**Path B — In-process llama.cpp (no extra daemon):**
```
$HERMES_HOME/iconic/venv/bin/pip install llama-cpp-python
# download gemma-2-2b-it Q4_K_M GGUF (accept the Gemma license on the source first):
mkdir -p $HERMES_HOME/iconic/models
# place: $HERMES_HOME/iconic/models/gemma-2-2b-it-Q4_K_M.gguf  (~1.7 GB)
```
**Verify:** the GGUF file exists and is ~1.6–1.8 GB; `$HERMES_HOME/iconic/venv/bin/python -m
hermes_iconic_memory.check_dreamer --model $HERMES_HOME/iconic/models/gemma-2-2b-it-Q4_K_M.gguf` loads it
on CPU and prints a one-line test completion.

### 3.4 Install the plugin into Hermes
```
mkdir -p "$HERMES_HOME/plugins/hermes-iconic-memory"
"$HERMES_HOME/iconic/venv/bin/python" -m hermes_iconic_memory.install_plugin --hermes-home "$HERMES_HOME"
```
The scan reads only the **first 8 KB** of `__init__.py`, so the marker must appear near the
top — a `MemoryProvider` subclass declared after a long licence header or a block of imports
is not seen, and the plugin is skipped without a message.

The directory must contain an `__init__.py` exposing `register_memory_provider` or a
`MemoryProvider` subclass — discovery is a text scan for those names, so a package without them is
skipped silently.

Then select it as the active provider (enabling a plugin does not select it):
```
hermes config set memory.provider hermes-iconic-memory
```
> **The `hermes iconic …` verbs below assume the plugin registers its CLI command as
> `iconic`.** The subcommand name is whatever the plugin passes to
> `register_cli_command(name=...)`, not a fixed value — a build that registers under the
> full plugin name answers to `hermes hermes-iconic-memory …` instead, and a provider
> routed through memory discovery may register no CLI command at all, leaving only
> `hermes memory …`. Confirm with `hermes --help` before scripting any of them.

**Verify:** `hermes memory status` reports `hermes-iconic-memory` as the active provider. Selection
can also be done interactively with `hermes memory setup`.

### 3.5 Configuration (explain each choice to the human as you set it)
Config lives at `$HERMES_HOME/iconic/config.yaml` — derive every path from the `hermes_home`
passed to `initialize()`, never a fixed `~/.hermes`, or separate profiles will share one store. Generate a default, then confirm the key fields:
```
$HERMES_HOME/iconic/venv/bin/python -m hermes_iconic_memory.init_config --mode <full|recall-only>
```
| Field | Default | Meaning / when to change |
|---|---|---|
| `db_backend` | `sqlite` | `sqlite` = one file, zero-ops. Switch to `mariadb` only for huge corpora / multi-agent. |
| `db_path` | `$HERMES_HOME/iconic/memory.db` | where memory lives; back this up. |
| `embedder` | `fastembed:bge-small-en-v1.5` | the recall model; leave as-is. |
| `dreamer` | `ollama:gemma2:2b` *or* `llama:<gguf path>` *or* `none` | `none` = recall-only mode. |
| `cpu_affinity` | auto (leave N−1 cores for the user) | pin the dreamer so it never fights chat models. |
| `recall.budget_ms` | `400` | recall fail-open deadline; raise only on a very slow disk. |
| `recall.weights` | `cos 0.6 / sal 0.25 / rec 0.15` | ranking blend; leave as-is. |
| `sleep.schedule` | `daily 04:00` (or on-idle) | when maintenance runs. |
**Verify:** `$HERMES_HOME/iconic/venv/bin/python -m hermes_iconic_memory.doctor` → all green.

### 3.6 Activate
```
hermes plugins enable hermes-iconic-memory
```
**Verify:** `hermes plugins status` shows it **active** and single-selected as the memory provider.

### 3.7 Smoke test (prove it works end to end)
1. **Round-trip:** in a Hermes session, have the agent call `remember("smoke-test: the user's
   project is named Odyssey")`, then in a *new* session ask "what's my project named?" → recall
   surfaces it. ✅
2. **Auto-capture (full mode):** hold a short multi-turn chat stating a durable fact, end the
   session, wait, then `hermes iconic stats` shows the new episodic entry (background dreamer ran). ✅
3. **Fail-open:** confirm a normal reply is never blocked — responses return immediately even while
   the dreamer is working. ✅
4. **Recall-only mode:** steps 1 + 3 only (no step 2 expected). ✅

### 3.8 Install the winnow skill (not optional)

```
mkdir -p "$HERMES_HOME/skills/winnow"
cp winnow-SKILL.md "$HERMES_HOME/skills/winnow/SKILL.md"
```
**Verify:** the agent lists `winnow` among its skills.

Without it the store still runs, and degrades quietly: memories written past the embed cap that
nothing can ever find, dated status pinned into permanence, two memories both claiming to be current.
None of that raises an error — the store simply gets harder to find anything in.

### 3.9 Prove the two things that fail silently

These are the checks worth doing by hand, because both failures look exactly like success.

**Retention ships disabled.** The store initialises with `retention.enabled: false`. Nothing below
runs a pass that can archive until the two signals are proven, and the order is the point: a
maintenance run that archives is the very event these checks exist to prevent.

**1 — Reinforcement actually raises a salience.** Recall something, then run the reinforce stage
*alone* — never a full pass, which would archive:
```
hermes iconic recall "<anything you have stored>"
hermes iconic sleep --reinforce-only
hermes iconic stats --salience-max
```
**Verify:** the maximum salience of an unpinned memory exceeds its starting value. If nothing has
ever risen, the recall log is not being written — a swallowed exception on that path is the usual
cause — and retention would run as a blind age clock.

**2 — Last use is being recorded.** Ask what a retention pass *would* take, without taking it:
```
hermes iconic sleep --dry-run
```
**Verify:** it reports a small share of the store, under the archive-wave guard. A store that would
archive nearly everything is telling you the last-use column was never written, so every memory has
fallen back to its creation date. **Baseline the column, then re-run the dry run.** Do not widen the
retention window to make the warning go away.

**3 — Only now, enable retention and take one supervised pass:**
```
hermes iconic config set retention.enabled true
hermes iconic sleep
```
**Verify:** archived counts match what the dry run predicted, and each archived row has a restorable
copy.

### 3.10 (Optional) schedule maintenance

Schedule only after step 3 has run once and been inspected — never before.
```
# cron the nightly sleep (full mode):
(crontab -l 2>/dev/null; echo "0 4 * * * $HERMES_HOME/iconic/venv/bin/python -m hermes_iconic_memory.sleep") | crontab -
```
**Verify:** `hermes iconic sleep --dry-run` reports the actions it would take and exits 0.

---

## Phase 4 — Handoff

Tell the human, briefly:
- ✅ Installed and verified, in **<full / recall-only>** mode.
- **Inspect:** `hermes iconic stats`. **Back up:** `hermes iconic export` (writes plain-text
  Markdown). **Health:** `hermes iconic doctor`.
- **Uninstall is clean:** disable the plugin (`hermes plugins disable hermes-iconic-memory`) and
  remove `$HERMES_HOME/plugins/hermes-iconic-memory/`. Hermes' native memory is untouched.
- If they were 🟡/recall-only: "You can switch to full mode later by setting `dreamer:` in the config
  and re-running `doctor` — no reinstall."

---

## Failure handling (the agent's rules)

- **A verify step fails → stop, show the human the exact command + output, propose the fix, ask before
  retrying.** Do not push forward on a red step.
- **Dreamer too slow / OOM at runtime → fall back to recall-only** (`dreamer: none`) and tell the
  human; don't let it wedge.
- **`is_available()` / doctor reports a missing piece → name the missing piece and the one command to
  get it** (e.g. "ollama isn't installed — `https://ollama.com/download`"), then resume.
- **Never** fabricate success. A step is done only when its **observed** output matches the expected
  result.
