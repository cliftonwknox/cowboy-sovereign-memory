"""Sleep — the nightly self-tending cycle. Idempotent; safe to re-run.

Order matters: **reinforce** (protect what got reused) BEFORE **decay**, then
**expire/archive** (move, never delete — I3), then **propose** (promote / merge /
consolidate) and **conflict-detect**. Everything in the propose/conflict stages only
*proposes* — a human (or you, with judgment) approves later (the judged gate, I4).
The cognitive stages (consolidate, conflict) are skipped on the Lite tier (no dreamer).
"""
from __future__ import annotations

import numpy as np

from memory import dreamer, maintenance
from memory.config import load
from memory.store import open_store

PROMOTE_SALIENCE = 1.5
MERGE_COS = 0.98
CONSOLIDATE_LO, CONSOLIDATE_HI = 0.85, 0.97
CONFLICT_COS = 0.84

# Unrecalled episodic memory reaches the archive floor in ~3 weeks; a single
# recall buys back several nights, so use outlives age.
DECAY_FACTOR = 0.95
ARCHIVE_FLOOR = 0.35

_CONS_SYS = ("Several related memory notes follow. Synthesize ONE durable lesson that "
             'captures them. Output ONLY JSON: {"summary": one sentence, "content": '
             'two or three sentences}.')
_CONF_SYS = ("Two dated memory notes follow. Decide whether they CONTRADICT (not merely "
             "differ). These notes record work over time, so the later note usually "
             "SUPERSEDES the earlier one: a plan that changed, a later stage of the same "
             "task, or a status that advanced is NOT a contradiction. Answer true only if "
             "both cannot have been true when they were written. "
             'Output ONLY JSON: {"contradict": boolean, "severity": "high"|"medium"|"low", '
             '"detail": string}.')


def _unit_matrix(items):
    if not items:
        return np.zeros((0, 1))
    M = np.array([i["embedding"] for i in items], dtype=float)
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return M / norms                                    # rows unit-length → dot = cosine


def propose_promotions(store) -> int:
    n = 0
    for e in store.active_with_vectors("episodic"):
        if e["salience"] >= PROMOTE_SALIENCE and not store.has_proposal("promote", e["id"]):
            store.add_proposal("promote", e["id"], None, {"salience": e["salience"]})
            n += 1
    return n


def propose_merges(store) -> int:
    sem = store.active_with_vectors("semantic")
    if len(sem) < 2:
        return 0
    S = _unit_matrix(sem) @ _unit_matrix(sem).T
    n = 0
    for i in range(len(sem)):
        for j in range(i + 1, len(sem)):
            if float(S[i, j]) >= MERGE_COS and not store.has_proposal("merge", sem[j]["id"]):
                store.add_proposal("merge", sem[j]["id"], sem[i]["id"], {"cos": float(S[i, j])})
                n += 1
    return n


def propose_consolidations(store, cfg) -> int:
    if not cfg.has_dreamer:
        return 0
    sem = store.active_with_vectors("semantic")
    if len(sem) < 3:
        return 0
    S = _unit_matrix(sem) @ _unit_matrix(sem).T
    used, made = set(), 0
    for i in range(len(sem)):
        if i in used:
            continue
        cluster = [i] + [j for j in range(len(sem)) if j != i and i not in used
                         and CONSOLIDATE_LO <= float(S[i, j]) <= CONSOLIDATE_HI]
        if len(cluster) < 3:
            continue
        # Anchor the proposal to the cluster's seed — one cluster is built per seed,
        # so it identifies the cluster without colliding with a different one. Without
        # an anchor the row carries NULL keys, which never collide, so the same cluster
        # is proposed again every night; and the check must precede the model call,
        # which is the expensive part.
        anchor = sem[cluster[0]]["id"]
        if store.has_proposal("consolidate", anchor):
            used.update(cluster)
            continue
        notes = "\n".join(f"- {sem[k]['summary']}: {sem[k]['content'][:200]}" for k in cluster)
        out = dreamer.extract_json_object(dreamer.chat(_CONS_SYS, notes, cfg, max_tokens=300))
        if out.get("summary") and out.get("content"):
            store.add_proposal("consolidate", anchor, None,
                               {"summary": out["summary"], "content": out["content"],
                                "sources": [sem[k]["id"] for k in cluster]})
            used.update(cluster)
            made += 1
    return made


def detect_conflicts(store, cfg) -> int:
    if not cfg.has_dreamer:
        return 0
    sem = store.active_with_vectors("semantic")
    if len(sem) < 2:
        return 0
    S = _unit_matrix(sem) @ _unit_matrix(sem).T
    made = 0
    for i in range(len(sem)):
        for j in range(i + 1, len(sem)):
            if float(S[i, j]) < CONFLICT_COS or store.has_conflict(sem[i]["id"], sem[j]["id"]):
                continue
            note = (f"NOTE 1 ({str(sem[i]['created_at'])[:10]}): {sem[i]['summary']}\n"
                    f"NOTE 2 ({str(sem[j]['created_at'])[:10]}): {sem[j]['summary']}")
            v = dreamer.extract_json_object(dreamer.chat(_CONF_SYS, note, cfg, max_tokens=200))
            if v.get("contradict"):
                sev = v.get("severity", "medium")
                sev = sev if sev in ("high", "medium", "low") else "medium"
                store.add_conflict(sem[i]["id"], sem[j]["id"], sev, str(v.get("detail", "")))
                made += 1
    return made


def run() -> str:
    cfg = load()
    store = open_store(cfg)
    try:
        log = [f"reinforced {store.reinforce()}"]
        store.decay(DECAY_FACTOR)
        log.append("decayed")
        # A wave far larger than a night's natural staleness means a tunable moved,
        # so hold the archive and report rather than acting on it.
        safe, held = maintenance.archive_wave_is_safe(store, ARCHIVE_FLOOR, DECAY_FACTOR)
        log.append(f"archived {store.expire_and_archive(ARCHIVE_FLOOR)}" if safe else "archive HELD")
        log.append(f"promotions {propose_promotions(store)}")
        log.append(f"merges {propose_merges(store)}")
        log.append(f"consolidations {propose_consolidations(store, cfg)}")
        log.append(f"conflicts {detect_conflicts(store, cfg)}")
        log.append(f"active {store.counts()}")

        stats = " | ".join(log)
        summary, items = maintenance.run(store, cfg, stats=f"STATS: {stats}", held=held)
        return "\n".join([stats, summary, *(f"  * {i}" for i in items)])
    finally:
        store.close()
