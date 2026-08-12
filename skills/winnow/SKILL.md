---
name: winnow
description: Use whenever you write a memory to the sovereign store, or work the store itself — choosing the layer, writing a summary that can actually be found, staying inside the embed cap, splitting what is too long, retiring finished work, resolving conflicts, and changing any retention rule. The care discipline that keeps a memory store worth having.
---

# Winnow — writing and tending a memory store

To winnow is to separate what still feeds you from the chaff. A memory store needs both
halves of that: **planting** (writing memories that can be found again) and **winnowing**
(clearing away what has finished, so what remains can surface).

A store that is only ever written to fails quietly. It does not throw errors — it just
gets harder to find anything in, until the answer you need is technically present and
practically invisible.

Every rule here repairs a specific failure mode. None of it is style preference.

---

# Part 1 — Planting: writing a memory that can be found

## 1. Should this exist at all?

Not if the repo, its history, or the project's own docs already record it. Not if it only
matters to the current conversation. If your human asks you to remember something that is
already written down elsewhere, capture what was **non-obvious** about it instead.

## 2. Search before you write

Search the store for the topic first. If a memory already covers it, **update that one by
its key** rather than adding a second. Two memories on one subject split the vector
between them and both rank worse than the single memory would have.

## 3. Choose the layer — this decides whether it is permanent

| | `semantic` | `episodic` |
|---|---|---|
| Lifecycle | **durable** — the long-lived layer | ages out when unused |
| Holds | standing rules, preferences, architecture, lessons | status, progress, session state, what shipped |

**The test: would this read as stale in a month? Then it is episodic.**

If deliberate writes all land in the durable layer, the store fills with dated status
notes that nothing can ever age out — and an old note claiming to describe the *current*
state will go on contradicting reality indefinitely. Permanence is a choice. Make it
deliberately.

`pinned` exempts a memory from **both** decay and archiving. Standing facts only — never
a work log.

## 4. Write the summary as the search query you would type later

The summary is what ranks. It is embedded first and it survives truncation, so it is the
part that decides whether the memory is ever found.

Lead with the plain subject, in the words someone would actually ask in, then the
specifics.

- **Bad:** `reflections` — a one-word summary on a long body. Nothing can find it.
- **Bad:** `Maintenance 2026-05-04: 0 fixed, 2 need review` — counts carry no meaning to
  match against. A summary like this ranks below the top ten for its own subject.
- **Good:** `Nightly maintenance report 2026-05-04 — memory store health check` — the
  same memory, reaching first place across several different phrasings.

## 5. Measure. Do not estimate.

```
len(summary) + 1 + len(content) <= EMBED_CAP        # 1400 by default
```

The embedder is only ever offered the first `EMBED_CAP` characters of summary + content.
Everything past that is stored and readable but **can never be matched by a search**.

Eyeball estimates run consistently over. Compute it. The write tool reports the overflow
it just created — **a write that returns a warning is not finished.**

Note the cap is a rough proxy for a token budget: token-dense text (hashes, paths, version
strings) packs far more tokens per character, so such content may be truncated even
shorter.

## 6. Give it a stable key

A kebab-case slug that identifies the subject. Without one, the memory cannot be updated
later — and the next write on the same subject invents a different slug and silently
creates a duplicate. Keys are idempotent only on an exact match, so reuse the existing
key **exactly** when updating.

## 7. Read back what you stored

Confirm the stored text ends where your content ends. A malformed write can carry
transport markup into the content field, and can silently drop the flags you passed with
it.

## When it will not fit: split at topic seams

**Never trim, never append.**

Trimming deletes the specifics that made the memory worth keeping. Appending is worse: one
vector is a single average, so a bundle of topics matches nothing well, and everything past
the cap is invisible anyway.

A seam is a subject boundary — one memory per thing someone would ask about separately.
Cross-link the halves.

> A restore runbook plus a warning that one backup location has gone stale is **two**
> memories. Someone asks *"how do I restore?"* or *"what's wrong with that backup?"* —
> never both at once.

Splitting can score *worse* if you cut the trigger vocabulary out of the half that should
own it. **Re-run the failing search afterward** and confirm the right half wins.

---

# Part 2 — Winnowing: tending the store

## The first law: instrumentation before retention

**Never enable a rule that decides what is kept until the signal it reads has actually
been recorded.**

Two ways this goes wrong, each capable of taking most of a store in a single pass:

- A decay fuse is shortened while reinforcement has never once raised a salience — every
  memory sits at its starting value, so the whole population crosses the floor together.
- Archiving is switched to last-use while the last-use column has never been written (a
  silently swallowed exception on the recall path is enough) — every memory falls back to
  its creation date, so the entire store looks abandoned at once.

Both are caught the same way: before enabling the rule, ask **"what would this do right
now?"** and count the blast radius. Both are fixed the same way: **baseline the signal to
now**, so the clock starts from working instrumentation.

A signal that was never recorded is not evidence of abandonment.

If the nightly run reports that it **held** an unusually large archive wave, this is the
first thing to suspect. Do not widen the window to silence it.

## What decides survival: last use, not age

A memory untouched for its window is archived however old or new it is; one still being
recalled survives indefinitely. **Usefulness keeps a memory alive** — which means a
genuinely useful memory needs no protection, it saves itself by being found.

Salience and decay only **order** search results. They do not decide what is kept.

**Archiving never deletes.** The row is copied whole — key, dates, and the reason it was
retired — so it can be restored. That is what makes a wrong call recoverable, and it is
why acting beats hoarding.

## Pinning is the only permanent choice

Pin **standing rules, preferences, safety facts** — things that must survive even if
nothing asks for them for a year. Nothing else.

Do not pin work logs, status, release records, or session anchors. They are the single
largest source of permanent clutter: resume anchors and "start here next session" notes,
pinned into permanence while the work they describe closes weeks later.

**Unpinning is safe and self-correcting.** When torn between "pin forever" and "let it
prove itself", choose the latter.

## Triage before you split

For a memory whose tail is past the embed cap:

1. **Is it still true?** Superseded or dated → unpin and let last-use retire it. Most
   over-cap memories are finished work, and splitting one only preserves dead detail in
   searchable form.
2. **Is it unpinned?** Then it needs no action — it retires on its own.
3. **Still true *and* pinned?** Only now is splitting worth the effort, because pinned
   never retires, so its hidden tail is a permanent loss.

## Judging what to retire — err toward keeping

**No automated classifier does this reliably.** Expect these to fail:

- a keyword filter matches durable standing rules and would retire them;
- the `kind` field is near-useless when most rows carry the default;
- filtering on *"does not look like a lesson"* retires technical gotchas, process rules,
  and infrastructure references.

What works is **positive identification**: archive only what actively identifies itself as
a record of closed work — a shipped release, a completed build, a sign-off, a resume
anchor — and keep everything that states something meant to keep holding. Expect it to
keep the clear majority of what it examines; if it selects most of them, the pattern is
too broad. **Read a sample of what it selected before letting it run.**

The asymmetry is the whole point: **wrongly keeping a work record costs nothing; wrongly
retiring a lesson loses it silently**, because you never learn what you no longer have.

The line to hold: **a finished thing is state; the rule learned from it is durable.**
*"Build complete"* goes. *"A guard is worthless if the input is authored by the party
being checked"* stays.

## Never leave two memories claiming to be current

A durable memory never ages out on its own, so a stale one misleads indefinitely.

Watch for an older memory that still announces itself as `CURRENT` while a later one
reverses the practice it describes. Nothing retires the older one, so it goes on
instructing future sessions to do the thing that is now forbidden.

When one supersedes another: mark the loser **in its summary**, **re-embed it** so the
marker is searchable, and pin the winner if it is a standing rule. Reconcile explicitly —
never silently clobber, and never leave both standing.

The dangerous shape is a **pinned memory that is the older side** of a contradiction:
permanent misinformation. Check for that first; it is cheap, and it is the only case that
cannot fix itself.

## Queues need a consumer

The nightly pass files proposals and conflicts for a human to judge. Both can accumulate
for months when **nothing drains them** — if no code reads a decision, entries pile up
unseen while looking like diligence.

Before adding anything that files work for later judgement, ask what will consume it.
When a queue exists, work it: an entry nobody has looked at in two months is telling you
something.

Watch for a queue re-filing the same item. Rows keyed on columns left NULL never collide,
so a de-duplicating unique index silently does nothing and the same work is proposed again
every night — expensive when each entry costs a model call. Give every queued row a stable
key derived from what it is about, and check for an existing entry **before** doing the
expensive work, not after.

## Trust counts, not reports

A bulk archive can report `0` while having moved a hundred rows; the return value of a
bulk statement is not evidence. Count the rows before and after, and confirm the archive
copy exists. Verify by measuring the store, never by reading a tool's return value.

## Columns that are not evidence

Some columns look like usage data and are not — a recall counter that nothing increments
still holds plausible historical values, so it reads as evidence of use. Before trusting
any column as a signal, confirm something actually writes it.

---

## The checklist — before every write

- [ ] Not already in the repo, its history, or another memory
- [ ] Searched for a conflicting or duplicate memory first
- [ ] Layer chosen deliberately — `episodic` if it would read as stale in a month
- [ ] Summary leads with the subject, in an asker's words
- [ ] `len(summary) + 1 + len(content) <= EMBED_CAP`, **computed**
- [ ] Stable key set, and reused exactly if updating
- [ ] Split at topic seams if it did not fit, halves cross-linked
- [ ] Anything it supersedes is marked and re-embedded
- [ ] Pinned only if it must outlive everything
- [ ] Read the stored row back — no stray markup, no truncation warning
