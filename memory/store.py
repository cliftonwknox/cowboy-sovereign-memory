"""The store abstraction — the keystone of portability.

One interface (`Store`), two backends:
  - `SqliteVecStore`  : portable default. Embedded, one file, no server.
  - `MariaDBStore`    : power option. Native VECTOR, server-class.

Recall ranks in Python (cosine from the store + salience + recency), so the only
thing a backend must do well is **vector KNN + simple CRUD**. Adding a new backend
(DuckDB-VSS, pgvector, …) means implementing this interface and nothing else.

Invariants honored here: I2 (every row carries its embed_model_id; search filters to
the active embedder) and the archive-not-delete shape for I3 (see `archive`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Candidate:
    id: int
    summary: str
    content: str
    cosine: float                 # 1.0 = identical direction
    salience: float
    last_recalled_at: Optional[str]


class Store:
    """Backend interface. Implement these; recall/capture/sleep use only this."""

    def init_schema(self) -> None: ...
    def write_engram(self, *, layer: str, kind: str, content: str, summary: str,
                     embedding: list[float], embed_model_id: str, embed_dim: int,
                     origin: str = "judged", confidence: str = "medium",
                     pinned: bool = False) -> int: ...
    def search(self, query_vec: list[float], embed_model_id: str, k: int,
               layers: Optional[tuple[str, ...]] = None) -> list[Candidate]: ...
    def get(self, engram_id: int) -> Optional[dict]: ...
    def log_recall(self, engram_id: int, score: float) -> None: ...
    def close(self) -> None: ...


def open_store(cfg) -> "Store":
    if cfg.store_backend == "mariadb":
        return MariaDBStore(cfg)
    return SqliteVecStore(cfg)


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

    def init_schema(self) -> None:
        from pathlib import Path
        sql = (Path(__file__).resolve().parent.parent / "sql" / "schema.sqlite.sql").read_text()
        self.conn.executescript(sql)
        self.conn.commit()

    def write_engram(self, *, layer, kind, content, summary, embedding, embed_model_id,
                     embed_dim, origin="judged", confidence="medium", pinned=False) -> int:
        cur = self.conn.execute(
            "INSERT INTO engram (layer,kind,content,summary,embed_model_id,embed_dim,"
            "origin,confidence,pinned) VALUES (?,?,?,?,?,?,?,?,?)",
            (layer, kind, content, summary, embed_model_id, embed_dim, origin, confidence,
             int(pinned)))
        eid = cur.lastrowid
        self.conn.execute("INSERT INTO vec_engram(rowid, embedding) VALUES (?, ?)",
                          (eid, self._ser(embedding)))
        self.conn.commit()
        return eid

    def search(self, query_vec, embed_model_id, k, layers=None) -> list[Candidate]:
        # Over-fetch by vector, then join + filter (state/model/layer) and keep top k.
        rows = self.conn.execute(
            "SELECT v.rowid AS id, v.distance AS dist, e.summary, e.content, e.salience, "
            "e.last_recalled_at, e.state, e.embed_model_id, e.layer "
            "FROM vec_engram v JOIN engram e ON e.id = v.rowid "
            "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (self._ser(query_vec), max(k * 4, 20))).fetchall()
        out = []
        for r in rows:
            if r["state"] != "active" or r["embed_model_id"] != embed_model_id:
                continue
            if layers and r["layer"] not in layers:
                continue
            out.append(Candidate(r["id"], r["summary"], r["content"],
                                 1.0 - float(r["dist"]), float(r["salience"]),
                                 r["last_recalled_at"]))
            if len(out) >= k:
                break
        return out

    def get(self, engram_id) -> Optional[dict]:
        r = self.conn.execute("SELECT * FROM engram WHERE id=?", (engram_id,)).fetchone()
        return dict(r) if r else None

    def log_recall(self, engram_id, score) -> None:
        self.conn.execute("INSERT INTO recall_log (engram_id, score) VALUES (?,?)",
                          (engram_id, score))
        self.conn.execute("UPDATE engram SET last_recalled_at=datetime('now') WHERE id=?",
                          (engram_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


# --------------------------------------------------------------------------- #
# MariaDB >= 11.7 native VECTOR (power option)
# --------------------------------------------------------------------------- #
class MariaDBStore(Store):
    def __init__(self, cfg):
        import mariadb  # pip install mariadb
        self.cfg = cfg
        self.conn = mariadb.connect(host=cfg.db_host, user=cfg.db_user,
                                    password=cfg.db_password, database=cfg.db_name)

    def init_schema(self) -> None:
        from pathlib import Path
        sql = (Path(__file__).resolve().parent.parent / "sql" / "schema.mariadb.sql").read_text()
        cur = self.conn.cursor()
        for stmt in [s for s in sql.split(";\n") if s.strip()]:
            cur.execute(stmt)
        self.conn.commit()

    def write_engram(self, *, layer, kind, content, summary, embedding, embed_model_id,
                     embed_dim, origin="judged", confidence="medium", pinned=False) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO engram (layer,kind,content,summary,embedding,embed_model_id,"
            "embed_dim,origin,confidence,pinned) VALUES "
            "(?,?,?,?,VEC_FromText(?),?,?,?,?,?)",
            (layer, kind, content, summary, json.dumps(embedding), embed_model_id,
             embed_dim, origin, confidence, int(pinned)))
        self.conn.commit()
        return cur.lastrowid

    def search(self, query_vec, embed_model_id, k, layers=None) -> list[Candidate]:
        cur = self.conn.cursor(dictionary=True)
        layer_clause = ""
        params = [json.dumps(query_vec), embed_model_id]
        if layers:
            layer_clause = " AND layer IN (" + ",".join(["?"] * len(layers)) + ")"
            params.extend(layers)
        params.append(max(k * 4, 20))
        cur.execute(
            "SELECT id, summary, content, salience, last_recalled_at, "
            "VEC_DISTANCE_COSINE(embedding, VEC_FromText(?)) AS dist "
            "FROM engram WHERE state='active' AND embed_model_id=?" + layer_clause +
            " ORDER BY dist LIMIT ?", params)
        return [Candidate(r["id"], r["summary"], r["content"], 1.0 - float(r["dist"]),
                          float(r["salience"]), r["last_recalled_at"])
                for r in cur.fetchall()][:k]

    def get(self, engram_id) -> Optional[dict]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM engram WHERE id=?", (engram_id,))
        return cur.fetchone()

    def log_recall(self, engram_id, score) -> None:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO recall_log (engram_id, score) VALUES (?,?)", (engram_id, score))
        cur.execute("UPDATE engram SET last_recalled_at=NOW() WHERE id=?", (engram_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
