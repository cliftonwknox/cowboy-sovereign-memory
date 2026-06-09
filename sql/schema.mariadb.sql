-- Cowboy Claude's Sovereign Memory — MariaDB >= 11.7 schema (POWER OPTION, native VECTOR)
-- Only for workstations / large corpora. The portable default is sqlite-vec (schema.sqlite.sql).

CREATE TABLE IF NOT EXISTS engram (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  layer            ENUM('episodic','semantic') NOT NULL,
  kind             VARCHAR(64)  NOT NULL DEFAULT 'note',
  content          MEDIUMTEXT   NOT NULL,
  summary          VARCHAR(512) NOT NULL,
  embedding        VECTOR(384)  NOT NULL,                       -- native MariaDB vector
  embed_model_id   VARCHAR(128) NOT NULL,                       -- I2: pinned to embedder
  embed_dim        INT          NOT NULL,
  salience         FLOAT        NOT NULL DEFAULT 1.0,
  confidence       ENUM('low','medium','high','pinned') NOT NULL DEFAULT 'medium',
  origin           VARCHAR(32)  NOT NULL DEFAULT 'judged',
  state            ENUM('active','superseded','archived') NOT NULL DEFAULT 'active',
  pinned           TINYINT      NOT NULL DEFAULT 0,
  created_at       DATETIME     NOT NULL DEFAULT NOW(),
  last_recalled_at DATETIME     NULL,
  expiry           DATETIME     NULL,
  name_key         VARCHAR(255) NULL,                           -- optional stable slug => idempotent re-write
  VECTOR INDEX (embedding) DISTANCE=cosine,
  INDEX idx_layer_state (layer, state),
  INDEX idx_model (embed_model_id),
  UNIQUE KEY uq_name_key (name_key)                             -- NULLs distinct => unnamed never collide
);

CREATE TABLE IF NOT EXISTS recall_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  engram_id BIGINT NOT NULL,
  recalled_at DATETIME NOT NULL DEFAULT NOW(),
  score FLOAT
);

CREATE TABLE IF NOT EXISTS engram_archive (
  id BIGINT PRIMARY KEY,
  layer VARCHAR(16), kind VARCHAR(64), content MEDIUMTEXT, summary VARCHAR(512),
  embed_model_id VARCHAR(128), embed_dim INT, salience FLOAT, origin VARCHAR(32),
  archived_at DATETIME NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS promotion_proposal (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  kind VARCHAR(16) NOT NULL,
  engram_id BIGINT, target_id BIGINT,
  signals JSON,
  decision ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  decided_by VARCHAR(64), decided_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conflict (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  engram_a BIGINT NOT NULL, engram_b BIGINT NOT NULL,
  severity ENUM('high','medium','low') NOT NULL DEFAULT 'medium',
  detail TEXT,
  state ENUM('open','resolved') NOT NULL DEFAULT 'open',
  created_at DATETIME NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS engram_link (
  from_id BIGINT NOT NULL, to_id BIGINT NOT NULL, relation VARCHAR(32) NOT NULL,
  PRIMARY KEY (from_id, to_id, relation)
);
