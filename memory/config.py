"""Config for Cowboy Claude's Sovereign Memory.

Portable + env-overridable. SQLite + sqlite-vec by default; MariaDB optional.
No machine-specific assumptions (no NUMA, no hardcoded paths, no required GPU).
A Lite tier simply leaves CCSM_DREAMER_URL empty — the cognitive layer is skipped.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("CCSM_DATA_DIR", str(ROOT / "data")))


@dataclass
class Config:
    # --- store backend ---
    store_backend: str = os.environ.get("CCSM_STORE", "sqlite")        # sqlite | mariadb
    sqlite_path: str = os.environ.get("CCSM_SQLITE_PATH", str(DATA / "memory.db"))
    db_host: str = os.environ.get("CCSM_DB_HOST", "127.0.0.1")
    db_user: str = os.environ.get("CCSM_DB_USER", "ccsm")
    db_password: str = os.environ.get("CCSM_DB_PASSWORD", "")
    db_name: str = os.environ.get("CCSM_DB_NAME", "ccsm")

    # --- embedder (required; small local model via llama.cpp or any OpenAI-style endpoint) ---
    embed_url: str = os.environ.get("CCSM_EMBED_URL", "http://127.0.0.1:8900")
    embed_model_id: str = os.environ.get("CCSM_EMBED_MODEL", "bge-small-en-v1.5")
    embed_dim: int = int(os.environ.get("CCSM_EMBED_DIM", "384"))

    # --- dreamer (OPTIONAL; empty = Lite tier, no cognition) ---
    dreamer_url: str = os.environ.get("CCSM_DREAMER_URL", "")
    dreamer_model_id: str = os.environ.get("CCSM_DREAMER_MODEL", "")

    # --- recall blend (relevance = cosine + salience + recency) ---
    w_cosine: float = float(os.environ.get("CCSM_W_COSINE", "0.60"))
    w_salience: float = float(os.environ.get("CCSM_W_SALIENCE", "0.25"))
    w_recency: float = float(os.environ.get("CCSM_W_RECENCY", "0.15"))
    top_k: int = int(os.environ.get("CCSM_TOP_K", "5"))
    recall_timeout_ms: int = int(os.environ.get("CCSM_RECALL_TIMEOUT_MS", "400"))  # I1 wall
    dedup_threshold: float = float(os.environ.get("CCSM_DEDUP", "0.97"))

    @property
    def has_dreamer(self) -> bool:
        """Full/Standard tier iff a dreamer endpoint is configured; else Lite."""
        return bool(self.dreamer_url.strip())


def load() -> Config:
    DATA.mkdir(parents=True, exist_ok=True)
    return Config()
