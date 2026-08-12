"""Nightly self-check over the memory store.

Deterministic checks only — no model call. Each check either repairs a mechanical
fault outright or records a finding for a human/agent to judge, and every check is
stateless so an unresolved finding is simply re-detected the next night. That is
what makes the nightly report safe to let decay: nothing is remembered once, it is
re-derived from the store each run.

Findings are written as one episodic, unpinned engram per night so the series ages
out through the ordinary decay/archive fuse instead of accumulating forever.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import re
import urllib.request

from memory.embed import EMBED_CAP

# Refuse to archive a wave larger than this share of the active store; a jump that
# large means a tunable moved, not that memory genuinely went stale.
ARCHIVE_WAVE_LIMIT = 0.10

# Dump locations that are expected to stay current.
BACKUP_DIRS = (
    "/mnt/storage/cowboy-memory-backups",
    "/mnt/grindhouse-backup/Nautilus-Backups/cowboy-memory-db",
    "/mnt/storage/COWBOY-MEMORY-EMERGENCY",
)
BACKUP_STALE_DAYS = 2

# Tool-call markup that leaks into content when a write is malformed; everything
# from the closing tag onward is transport, not memory.
_LEAK = re.compile(r"</content>\s*(\\n)?\s*<name_key>")


def _rows(store, sql: str, params: tuple = ()) -> list[tuple]:
    cur = store.conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def _scalar(store, sql: str, params: tuple = ()):
    rows = _rows(store, sql, params)
    return rows[0][0] if rows else None


# --------------------------------------------------------------------------- #
# repairs — mechanical, reversible, no judgement required
# --------------------------------------------------------------------------- #

def _reembed(store, cfg, ids: list) -> int:
    """Rebuild vectors from current text. Content edited without this stays searchable
    only by the text it used to hold."""
    from memory.embed import embed
    cur, done = store.conn.cursor(), 0
    for eid in ids:
        row = _rows(store, "SELECT summary, content FROM engram WHERE id=?", (eid,))
        if not row:
            continue
        try:
            vec = embed(f"{row[0][0]}\n{row[0][1]}", cfg, timeout=30)
        except Exception:
            continue  # a transient embedder failure is named by the health check
        cur.execute("UPDATE engram SET embedding=VEC_FromText(?), embed_dim=?, "
                    "embed_model_id=? WHERE id=?",
                    (json.dumps(vec), cfg.embed_dim, cfg.embed_model_id, eid))
        done += 1
    store.conn.commit()
    return done


def fix_leaked_markup(store, cfg) -> str | None:
    """Strip transport markup that leaked into stored content."""
    ids = [r[0] for r in _rows(
        store, "SELECT id FROM engram WHERE content LIKE '%</content>%<name_key>%'")]
    if not ids:
        return None
    cur, changed = store.conn.cursor(), []
    for eid in ids:
        content = _scalar(store, "SELECT content FROM engram WHERE id=?", (eid,))
        # The row filter is a loose LIKE; only count a row the strip actually altered,
        # so the report never claims a repair it did not make.
        stripped = _LEAK.split(content)[0].rstrip()
        if stripped != content:
            cur.execute("UPDATE engram SET content=? WHERE id=?", (stripped, eid))
            changed.append(eid)
    store.conn.commit()
    if not changed:
        return None
    return (f"stripped leaked markup from {len(changed)} engram(s) and re-embedded "
            f"{_reembed(store, cfg, changed)}: {changed[:8]}")


def fix_missing_vectors(store, cfg) -> str | None:
    """Re-embed engrams that carry no usable vector, which search cannot reach."""
    ids = [r[0] for r in _rows(
        store, "SELECT id FROM engram WHERE state='active' "
               "AND (embedding IS NULL OR embed_dim IS NULL OR embed_dim<>?)",
        (cfg.embed_dim,))]
    if not ids:
        return None
    done = _reembed(store, cfg, ids)
    return f"re-embedded {done} engram(s) that had no usable vector" if done else None


# --------------------------------------------------------------------------- #
# checks — reported for judgement, never auto-resolved
# --------------------------------------------------------------------------- #

def check_over_cap(store) -> str | None:
    """Content past the embed cap is stored but invisible to search."""
    over = "CHAR_LENGTH(summary)+1+CHAR_LENGTH(content)"
    row = _rows(store, f"SELECT COUNT(*), SUM({over}-?) FROM engram "
                       f"WHERE state='active' AND {over} > ?", (EMBED_CAP, EMBED_CAP))
    count, hidden = (row[0][0], row[0][1]) if row else (0, 0)
    if not count:
        return None
    # Report the whole population, not the sample — a capped list reads as the
    # total and hides the scale of the problem.
    worst = _rows(store, f"SELECT id, {over} AS n FROM engram WHERE state='active' "
                         f"AND {over} > ? ORDER BY n DESC LIMIT 5", (EMBED_CAP,))
    return (f"{count} engram(s) exceed the {EMBED_CAP}-char embed cap, hiding "
            f"{int(hidden or 0):,} unsearchable characters. Split along topic seams, do "
            f"not trim. Worst: " + ", ".join(f"{i}({n})" for i, n in worst))


def check_duplicate_keys(store) -> str | None:
    """A repeated name_key breaks idempotent update — one of the pair is unreachable."""
    rows = _rows(store, "SELECT name_key, COUNT(*) c FROM engram WHERE name_key IS NOT NULL "
                        "AND name_key<>'' AND state='active' GROUP BY name_key "
                        "HAVING c>1 LIMIT 10")
    if not rows:
        return None
    return "duplicate name_key(s), updates will hit only one: " + \
           ", ".join(f"{k}×{c}" for k, c in rows)


def check_unkeyed_judged(store) -> str | None:
    """A deliberate memory with no name_key cannot be updated in place, so the next
    write on the same subject invents a slug and silently adds a duplicate."""
    n = _scalar(store, "SELECT COUNT(*) FROM engram WHERE state='active' "
                       "AND origin='judged' AND (name_key IS NULL OR name_key='')") or 0
    if not n:
        return None
    worst = _rows(store, "SELECT id FROM engram WHERE state='active' AND origin='judged' "
                         "AND (name_key IS NULL OR name_key='') ORDER BY id DESC LIMIT 5")
    return (f"{n} deliberate engram(s) have no name_key and cannot be updated in place; "
            "a later write on the same subject will duplicate them instead. Recent: "
            + ", ".join(str(r[0]) for r in worst))


def check_reinforcement_live(store) -> str | None:
    """Salience must be able to rise; if it never does, decay is a blind age clock."""
    if _scalar(store, "SELECT COUNT(*) FROM engram WHERE state='active' AND pinned=0 "
                      "AND salience > 1.0"):
        return None
    logged = _scalar(store, "SELECT COUNT(*) FROM recall_log") or 0
    if not logged:
        return ("no recall has ever raised a salience and recall_log is empty — the "
                "reinforcement path is not writing; decay is running as a pure age clock")
    return None


def check_unwritten_required_columns(store) -> str | None:
    """A required column the code never names fails every insert into its table.

    Only tables the code actually writes are considered — a required column in a
    table nothing inserts into cannot break anything.
    """
    src = ""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                src += fh.read()
        except OSError:
            continue
    bad = []
    for table, col in _rows(store,
                            "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
                            "WHERE TABLE_SCHEMA=DATABASE() AND IS_NULLABLE='NO' "
                            "AND COLUMN_DEFAULT IS NULL AND EXTRA NOT LIKE '%auto_increment%'"):
        if f"INTO {table}" in src and col not in src:
            bad.append(f"{table}.{col}")
    if not bad:
        return None
    return ("required column(s) no code ever writes — any insert omitting them raises: "
            + ", ".join(bad[:8]))


def check_backups(store=None) -> str | None:
    """A dump directory that silently stops updating looks maintained until needed."""
    now, stale = datetime.datetime.now(), []
    for d in BACKUP_DIRS:
        dumps = glob.glob(os.path.join(d, "cowboy_memory-*.sql.gz"))
        if not dumps:
            stale.append(f"{os.path.basename(d)}: no dump")
            continue
        newest = max(os.path.getmtime(p) for p in dumps)
        age = (now - datetime.datetime.fromtimestamp(newest)).days
        if age > BACKUP_STALE_DAYS:
            stale.append(f"{os.path.basename(d)}: {age}d old")
    return "backup location(s) stale: " + "; ".join(stale) if stale else None


def check_review_backlog(store) -> str | None:
    """Proposals and conflicts are queued for judgement and never expire on their own."""
    props = _scalar(store, "SELECT COUNT(*) FROM promotion_proposal "
                           "WHERE decision='pending'") or 0
    conflicts = _scalar(store, "SELECT COUNT(*) FROM conflict WHERE state='open'") or 0
    if props + conflicts == 0:
        return None
    oldest = _scalar(store, "SELECT MIN(created_at) FROM promotion_proposal "
                            "WHERE decision='pending'")
    age = f", oldest {str(oldest)[:10]}" if oldest else ""
    return (f"awaiting judgement: {props} promotion/merge proposal(s), "
            f"{conflicts} conflict(s){age}")


def check_embedder(cfg) -> str | None:
    """Search and every write depend on the embedder answering."""
    url = (getattr(cfg, "embed_url", "") or "").rstrip("/")
    if not url:
        return None
    try:
        with urllib.request.urlopen(url + "/health", timeout=5) as r:
            if r.status != 200:
                return f"embedder returned HTTP {r.status}"
    except Exception as e:
        return f"embedder unreachable at {url}: {type(e).__name__}"
    return None


def archive_wave_is_safe(store, retention_days: dict) -> tuple[bool, str | None]:
    """Guard against a retention change retro-archiving a large share of the store."""
    active = _scalar(store, "SELECT COUNT(*) FROM engram WHERE state='active'") or 0
    if not active:
        return True, None
    doomed = sum(store.unused_since(layer, days) for layer, days in retention_days.items())
    if doomed <= active * ARCHIVE_WAVE_LIMIT:
        return True, None
    return False, (f"ARCHIVING HELD: this run would archive {doomed} of {active} active "
                   f"engrams ({doomed / active:.0%}), over the {ARCHIVE_WAVE_LIMIT:.0%} "
                   "limit. A retention window moved, or last-use was never recorded — "
                   "baseline last_recalled_at before letting this run")


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def _compose(fixes: list[str], findings: list[str], stats: str) -> tuple[str, str]:
    """Build a report that fits the embed cap, dropping detail before findings."""
    # Search ranks on summary + content, so both lead with the words someone
    # would actually ask in; counts alone carry no meaning to match against.
    summary = (f"Dreamer nightly maintenance report {datetime.date.today()} — memory store "
               f"health check: {len(fixes)} auto-fixed, {len(findings)} flagged for review")
    blocks = ["Nightly self-check of the memory store by the dreamer: problems it repaired "
              "on its own, and problems it wants reviewed."]
    if findings:
        blocks.append("NEEDS REVIEW:\n" + "\n".join(f"- {f}" for f in findings))
    if fixes:
        blocks.append("AUTO-FIXED:\n" + "\n".join(f"- {f}" for f in fixes))
    if not blocks:
        blocks.append("No faults found.")
    blocks.append(stats)
    blocks.append("Full detail: journalctl -u cowboy-sleep.service")
    content = "\n\n".join(blocks)
    budget = EMBED_CAP - len(summary) - 1
    if len(content) > budget:
        content = content[:budget - 30].rstrip() + "\n[truncated — see journal]"
    return summary, content


def run(store, cfg, *, stats: str = "", held: str | None = None) -> tuple[str, list[str]]:
    """Repair what is mechanical, report what needs judgement, file the report."""
    fixes, findings = [], [held] if held else []
    for repair in (lambda: fix_leaked_markup(store, cfg),
                   lambda: fix_missing_vectors(store, cfg)):
        try:
            if (msg := repair()):
                fixes.append(msg)
        except Exception as e:
            findings.append(f"repair step failed: {type(e).__name__}: {e}")
    for check in (lambda: check_over_cap(store), lambda: check_duplicate_keys(store),
                  lambda: check_unkeyed_judged(store),
                  lambda: check_reinforcement_live(store),
                  lambda: check_unwritten_required_columns(store),
                  lambda: check_backups(), lambda: check_review_backlog(store),
                  lambda: check_embedder(cfg)):
        try:
            if (msg := check()):
                findings.append(msg)
        except Exception as e:
            findings.append(f"check failed: {type(e).__name__}: {e}")

    summary, content = _compose(fixes, findings, stats)
    try:
        from memory.capture import remember
        remember(summary, content, kind="maintenance", pinned=False, layer="episodic",
                 name_key=f"dreamer-maintenance-{datetime.date.today()}")
    except Exception as e:
        findings.append(f"report not filed: {type(e).__name__}: {e}")
    return summary, fixes + findings
