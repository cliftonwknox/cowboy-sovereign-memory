"""The store abstraction — the keystone of portability.

One interface (`Store`), two backends:
  - `SqliteVecStore`  : portable default. Embedded, one file, no server.
  - `MariaDBStore`    : power option. Native VECTOR, server-class.

Recall ranks in Python (cosine from the store + salience + recency), so a backend only
needs **vector KNN + simple CRUD + a few bulk maintenance ops**. Adding a new backend
(DuckDB-VSS, pgvector, …) means implementing this interface and nothing else.

Invariants honored here: I2 (every row carries its embed_model_id; search filters to the
active embedder) and I3 (`expire_and_archive` MOVES rows to an archive table — it never
deletes durable memory; only the judged gate may supersede).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_SQL = Path(__file__).resolve().parent.parent / "sql"


@dataclass
class Candidate:
    id: int
    summary: str
    content: str
    cosine: float
    salience: float
    last_recalled_at: Optional[str]


class Store:
    """Backend interface. Recall / capture / sleep use ONLY these."""
    def init_schema(self) -> None: ...
    def write_engram(self, *, layer, kind, content, summary, embedding, embed_model_id,
                     embed_dim, origin="judged", confidence="medium", pinned=False,
                     name_key=None) -> int: ...
    def search(self, query_vec, embed_model_id, k, layers=None) -> list[Candidate]: ...
    def get(self, engram_id) -> Optional[dict]: ...
    def log_recall(self, engram_id, score) -> None: ...
    # --- sleep primitives ---
    def reinforce(self) -> int: ...
    def decay(self, factor: float = 0.97) -> None: ...
    def expire_and_archive(self, floor: float = 0.2) -> int: ...
    def active_with_vectors(self, layer: str) -> list[dict]: ...
    def has_proposal(self, kind: str, engram_id: int) -> bool: ...
    def add_proposal(self, kind: str, engram_id, target_id, signals: dict) -> None: ...
    def has_conflict(self, a: int, b: int) -> bool: ...
    def add_conflict(self, a: int, b: int, severity: str, detail: str) -> None: ...
    def counts(self) -> dict: ...
    def export_active(self) -> list[dict]: ...
    def close(self) -> None: ...


def open_store(cfg) -> "Store":
    return MariaDBStore(cfg) if cfg.store_backend == "mariadb" else SqliteVecStore(cfg)


# --------------------------------------------------------------------------- #
# SQLite + sqlite-vec (portable default)
# --------------------------------------------------------------------------- #
class SqliteVecStore(Store):
    def __init__(self, cfg):
        import sqlite3
        import sqlite_vec
        self.cfg = cfg
        self.conn = sqlite3.connect(cfg.sqlite_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
        self._ser = sqlite_vec.serialize_float32

    def init_schema(self):
        self.conn.executescript((_SQL / "schema.sqlite.sql").read_text())
        self.conn.commit()

    def write_engram(self, *, layer, kind, content, summary, embedding, embed_model_id,
                     embed_dim, origin="judged", confidence="medium", pinned=False,
                     name_key=None) -> int:
        # Idempotent when name_key is given: UPDATE the existing row's content/summary/
        # embedding ONLY — never the self-tending fields (salience/state/pinned/recall).
        if name_key:
            row = self.conn.execute(
                "SELECT id FROM engram WHERE name_key=?", (name_key,)).fetchone()
            if row:
                eid = row["id"]
                self.conn.execute(
                    "UPDATE engram SET content=?, summary=?, embed_model_id=?, embed_dim=? "
                    "WHERE id=?", (content, summary, embed_model_id, embed_dim, eid))
                self.conn.execute("DELETE FROM vec_engram WHERE rowid=?", (eid,))
                self.conn.execute("INSERT INTO vec_engram(rowid, embedding) VALUES (?, ?)",
                                  (eid, self._ser(embedding)))
                self.conn.commit()
                return eid
        cur = self.conn.execute(
            "INSERT INTO engram (layer,kind,content,summary,embed_model_id,embed_dim,"
            "origin,confidence,pinned,name_key) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (layer, kind, content, summary, embed_model_id, embed_dim, origin, confidence,
             int(pinned), name_key))
        eid = cur.lastrowid
        self.conn.execute("INSERT INTO vec_engram(rowid, embedding) VALUES (?, ?)",
                          (eid, self._ser(embedding)))
        self.conn.commit()
        return eid

    def search(self, query_vec, embed_model_id, k, layers=None) -> list[Candidate]:
        rows = self.conn.execute(
            "SELECT v.rowid AS id, v.distance AS dist, e.summary, e.content, e.salience, "
            "e.last_recalled_at, e.state, e.embed_model_id, e.layer "
            "FROM vec_engram v JOIN engram e ON e.id=v.rowid "
            "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (self._ser(query_vec), max(k * 4, 20))).fetchall()
        out = []
        for r in rows:
            if r["state"] != "active" or r["embed_model_id"] != embed_model_id:
                continue
            if layers and r["layer"] not in layers:
                continue
            out.append(Candidate(r["id"], r["summary"], r["content"], 1.0 - float(r["dist"]),
                                 float(r["salience"]), r["last_recalled_at"]))
            if len(out) >= k:
                break
        return out

    def get(self, engram_id):
        r = self.conn.execute("SELECT * FROM engram WHERE id=?", (engram_id,)).fetchone()
        return dict(r) if r else None

    def log_recall(self, engram_id, score):
        self.conn.execute("INSERT INTO recall_log (engram_id, score) VALUES (?,?)",
                          (engram_id, score))
        self.conn.execute("UPDATE engram SET last_recalled_at=datetime('now') WHERE id=?",
                          (engram_id,))
        self.conn.commit()

    def reinforce(self) -> int:
        n = self.conn.execute(
            "SELECT COUNT(DISTINCT engram_id) FROM recall_log").fetchone()[0]
        self.conn.execute(
            "UPDATE engram SET salience = MIN(salience + 0.1*("
            "  SELECT COUNT(*) FROM recall_log WHERE recall_log.engram_id=engram.id), 3.0) "
            "WHERE id IN (SELECT DISTINCT engram_id FROM recall_log)")
        self.conn.execute("DELETE FROM recall_log")
        self.conn.commit()
        return n

    def decay(self, factor: float = 0.97):
        self.conn.execute("UPDATE engram SET salience=salience*? WHERE state='active' AND pinned=0",
                          (factor,))
        self.conn.commit()

    def expire_and_archive(self, floor: float = 0.2) -> int:
        where = "layer='episodic' AND state='active' AND pinned=0 AND salience < ?"
        self.conn.execute(
            "INSERT OR IGNORE INTO engram_archive "
            "(id,layer,kind,content,summary,embed_model_id,embed_dim,salience,origin) "
            f"SELECT id,layer,kind,content,summary,embed_model_id,embed_dim,salience,origin "
            f"FROM engram WHERE {where}", (floor,))
        cur = self.conn.execute(f"UPDATE engram SET state='archived' WHERE {where}", (floor,))
        self.conn.commit()
        return cur.rowcount

    def active_with_vectors(self, layer: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT e.id, e.summary, e.content, e.salience, vec_to_json(v.embedding) AS emb "
            "FROM engram e JOIN vec_engram v ON v.rowid=e.id "
            "WHERE e.layer=? AND e.state='active'", (layer,)).fetchall()
        return [{"id": r["id"], "summary": r["summary"], "content": r["content"],
                 "salience": r["salience"], "embedding": json.loads(r["emb"])} for r in rows]

    def has_proposal(self, kind, engram_id) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM promotion_proposal WHERE kind=? AND engram_id=? AND decision='pending'",
            (kind, engram_id)).fetchone() is not None

    def add_proposal(self, kind, engram_id, target_id, signals):
        self.conn.execute(
            "INSERT INTO promotion_proposal (kind,engram_id,target_id,signals) VALUES (?,?,?,?)",
            (kind, engram_id, target_id, json.dumps(signals)))
        self.conn.commit()

    def has_conflict(self, a, b) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM conflict WHERE (engram_a=? AND engram_b=?) OR (engram_a=? AND engram_b=?)",
            (a, b, b, a)).fetchone() is not None

    def add_conflict(self, a, b, severity, detail):
        self.conn.execute(
            "INSERT INTO conflict (engram_a,engram_b,severity,detail) VALUES (?,?,?,?)",
            (a, b, severity, detail[:2000]))
        self.conn.commit()

    def counts(self) -> dict:
        rows = self.conn.execute(
            "SELECT layer, COUNT(*) c FROM engram WHERE state='active' GROUP BY layer").fetchall()
        return {r["layer"]: r["c"] for r in rows}

    def export_active(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id,layer,kind,summary,content,confidence,origin,created_at "
            "FROM engram WHERE state='active' ORDER BY layer, id").fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()


# --------------------------------------------------------------------------- #
# MariaDB >= 11.7 native VECTOR (power option)
# --------------------------------------------------------------------------- #
class MariaDBStore(Store):
    def __init__(self, cfg):
        import mariadb
        self.cfg = cfg
        self.conn = mariadb.connect(host=cfg.db_host, user=cfg.db_user,
                                    password=cfg.db_password, database=cfg.db_name)

    def init_schema(self):
        cur = self.conn.cursor()
        for stmt in [s for s in (_SQL / "schema.mariadb.sql").read_text().split(";\n") if s.strip()]:
            cur.execute(stmt)
        self.conn.commit()

    def write_engram(self, *, layer, kind, content, summary, embedding, embed_model_id,
                     embed_dim, origin="judged", confidence="medium", pinned=False,
                     name_key=None) -> int:
        cur = self.conn.cursor()
        # Idempotent when name_key is given: UPDATE content/summary/embedding ONLY —
        # never the self-tending fields (salience/state/pinned/recall).
        if name_key:
            cur.execute("SELECT id FROM engram WHERE name_key=?", (name_key,))
            row = cur.fetchone()
            if row:
                eid = row[0]
                cur.execute(
                    "UPDATE engram SET content=?, summary=?, embedding=VEC_FromText(?), "
                    "embed_model_id=?, embed_dim=? WHERE id=?",
                    (content, summary, json.dumps(embedding), embed_model_id, embed_dim, eid))
                self.conn.commit()
                return eid
        cur.execute(
            "INSERT INTO engram (layer,kind,content,summary,embedding,embed_model_id,embed_dim,"
            "origin,confidence,pinned,name_key) VALUES (?,?,?,?,VEC_FromText(?),?,?,?,?,?,?)",
            (layer, kind, content, summary, json.dumps(embedding), embed_model_id, embed_dim,
             origin, confidence, int(pinned), name_key))
        self.conn.commit()
        return cur.lastrowid

    def search(self, query_vec, embed_model_id, k, layers=None) -> list[Candidate]:
        cur = self.conn.cursor(dictionary=True)
        clause, params = "", [json.dumps(query_vec), embed_model_id]
        if layers:
            clause = " AND layer IN (" + ",".join(["?"] * len(layers)) + ")"
            params += list(layers)
        params.append(max(k * 4, 20))
        cur.execute(
            "SELECT id, summary, content, salience, last_recalled_at, "
            "VEC_DISTANCE_COSINE(embedding, VEC_FromText(?)) AS dist FROM engram "
            "WHERE state='active' AND embed_model_id=?" + clause + " ORDER BY dist LIMIT ?", params)
        return [Candidate(r["id"], r["summary"], r["content"], 1.0 - float(r["dist"]),
                          float(r["salience"]), r["last_recalled_at"]) for r in cur.fetchall()][:k]

    def get(self, engram_id):
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM engram WHERE id=?", (engram_id,))
        return cur.fetchone()

    def log_recall(self, engram_id, score):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO recall_log (engram_id, score) VALUES (?,?)", (engram_id, score))
        cur.execute("UPDATE engram SET last_recalled_at=NOW() WHERE id=?", (engram_id,))
        self.conn.commit()

    def reinforce(self) -> int:
        cur = self.conn.cursor()
        n = cur.execute("SELECT COUNT(DISTINCT engram_id) FROM recall_log") or cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT engram_id) FROM recall_log"); n = cur.fetchone()[0]
        cur.execute("UPDATE engram e JOIN (SELECT engram_id, COUNT(*) c FROM recall_log "
                    "GROUP BY engram_id) r ON e.id=r.engram_id "
                    "SET e.salience=LEAST(e.salience+0.1*r.c, 3.0)")
        cur.execute("DELETE FROM recall_log")
        self.conn.commit()
        return n

    def decay(self, factor: float = 0.97):
        cur = self.conn.cursor()
        cur.execute("UPDATE engram SET salience=salience*? WHERE state='active' AND pinned=0",
                    (factor,))
        self.conn.commit()

    def expire_and_archive(self, floor: float = 0.2) -> int:
        cur = self.conn.cursor()
        where = "layer='episodic' AND state='active' AND pinned=0 AND salience < ?"
        cur.execute("INSERT IGNORE INTO engram_archive "
                    "(id,layer,kind,content,summary,embed_model_id,embed_dim,salience,origin) "
                    f"SELECT id,layer,kind,content,summary,embed_model_id,embed_dim,salience,origin "
                    f"FROM engram WHERE {where}", (floor,))
        cur.execute(f"UPDATE engram SET state='archived' WHERE {where}", (floor,))
        n = cur.rowcount
        self.conn.commit()
        return n

    def active_with_vectors(self, layer: str) -> list[dict]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT id, summary, content, salience, VEC_ToText(embedding) AS emb "
                    "FROM engram WHERE layer=? AND state='active'", (layer,))
        return [{"id": r["id"], "summary": r["summary"], "content": r["content"],
                 "salience": r["salience"], "embedding": json.loads(r["emb"])}
                for r in cur.fetchall()]

    def has_proposal(self, kind, engram_id) -> bool:
        cur = self.conn.cursor()
        # Any prior proposal (pending OR decided) blocks re-proposing — a rejected
        # promote/merge stays rejected and doesn't reappear next sleep cycle.
        cur.execute("SELECT 1 FROM promotion_proposal WHERE kind=? AND engram_id=?",
                    (kind, engram_id))
        return cur.fetchone() is not None

    def add_proposal(self, kind, engram_id, target_id, signals):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO promotion_proposal (kind,engram_id,target_id,signals) "
                    "VALUES (?,?,?,?)", (kind, engram_id, target_id, json.dumps(signals)))
        self.conn.commit()

    def has_conflict(self, a, b) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM conflict WHERE (engram_a=? AND engram_b=?) OR "
                    "(engram_a=? AND engram_b=?)", (a, b, b, a))
        return cur.fetchone() is not None

    def add_conflict(self, a, b, severity, detail):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO conflict (engram_a,engram_b,severity,detail) VALUES (?,?,?,?)",
                    (a, b, severity, detail[:2000]))
        self.conn.commit()

    def counts(self) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT layer, COUNT(*) FROM engram WHERE state='active' GROUP BY layer")
        return {row[0]: row[1] for row in cur.fetchall()}

    def export_active(self) -> list[dict]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT id,layer,kind,summary,content,confidence,origin,created_at "
                    "FROM engram WHERE state='active' ORDER BY layer, id")
        return cur.fetchall()

    def close(self):
        self.conn.close()
