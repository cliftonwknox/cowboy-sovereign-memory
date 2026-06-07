-- Cowboy Claude's Sovereign Memory — SQLite + sqlite-vec schema (PORTABLE DEFAULT)
-- Requires the sqlite-vec extension loaded at connection time (see memory/store.py).
-- One file, zero server. Runs identically on macOS / Linux / Windows.

CREATE TABLE IF NOT EXISTS engram (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    layer            TEXT    NOT NULL CHECK (layer IN ('episodic','semantic')),
    kind             TEXT    NOT NULL DEFAULT 'note',
    content          TEXT    NOT NULL,
    summary          TEXT    NOT NULL,
    embed_model_id   TEXT    NOT NULL,                 -- I2: vectors pinned to their embedder
    embed_dim        INTEGER NOT NULL,
    salience         REAL    NOT NULL DEFAULT 1.0,
    confidence       TEXT    NOT NULL DEFAULT 'medium',-- low|medium|high|pinned
    origin           TEXT    NOT NULL DEFAULT 'judged',-- judged|auto_extracted|consolidated|user
    state            TEXT    NOT NULL DEFAULT 'active',-- active|superseded|archived
    pinned           INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    last_recalled_at TEXT,
    expiry           TEXT
);
CREATE INDEX IF NOT EXISTS idx_engram_layer_state ON engram(layer, state);
CREATE INDEX IF NOT EXISTS idx_engram_model       ON engram(embed_model_id);

-- Vector index (sqlite-vec virtual table). rowid mirrors engram.id.
-- distance_metric=cosine so MATCH returns cosine distance (cosine_sim = 1 - distance).
CREATE VIRTUAL TABLE IF NOT EXISTS vec_engram USING vec0(
    embedding float[384] distance_metric=cosine
);

CREATE TABLE IF NOT EXISTS recall_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    engram_id   INTEGER NOT NULL,
    recalled_at TEXT    NOT NULL DEFAULT (datetime('now')),
    score       REAL
);

CREATE TABLE IF NOT EXISTS engram_archive (
    id          INTEGER PRIMARY KEY,
    layer       TEXT, kind TEXT, content TEXT, summary TEXT,
    embed_model_id TEXT, embed_dim INTEGER, salience REAL, origin TEXT,
    archived_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS promotion_proposal (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT    NOT NULL,                       -- promote|merge|consolidate
    engram_id  INTEGER,
    target_id  INTEGER,
    signals    TEXT,                                   -- JSON blob of evidence
    decision   TEXT    NOT NULL DEFAULT 'pending',     -- pending|approved|rejected
    decided_by TEXT, decided_at TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conflict (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    engram_a   INTEGER NOT NULL,
    engram_b   INTEGER NOT NULL,
    severity   TEXT    NOT NULL DEFAULT 'medium',      -- high|medium|low
    detail     TEXT,
    state      TEXT    NOT NULL DEFAULT 'open',         -- open|resolved
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS engram_link (
    from_id  INTEGER NOT NULL,
    to_id    INTEGER NOT NULL,
    relation TEXT    NOT NULL,                          -- consolidates|relates|supersedes
    PRIMARY KEY (from_id, to_id, relation)
);
