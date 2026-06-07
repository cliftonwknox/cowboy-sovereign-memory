"""The dreamer — a small local LLM used during extraction + sleep cognition.

OPTIONAL: the Lite tier has no dreamer (cfg.has_dreamer == False) and skips everything
here. stdlib urllib against an OpenAI-style /v1/chat/completions (llama.cpp server, LM
Studio, etc.). `thinking=False` asks reasoning models to skip the think block so we get
clean JSON. Fail-safe: returns "" on any error — cognition is best-effort.
"""
from __future__ import annotations

import json
import re
import urllib.request


def chat(system: str, user: str, cfg, *, max_tokens: int = 512, thinking: bool = False) -> str:
    payload = {
        "model": cfg.dreamer_model_id or "local",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens, "temperature": 0.2,
    }
    if not thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    try:
        req = urllib.request.Request(
            cfg.dreamer_url.rstrip("/") + "/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception:
        return ""


def extract_json_array(s: str) -> list:
    m = re.search(r"\[.*\]", s or "", re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else []
    except Exception:
        return []


def extract_json_object(s: str) -> dict:
    m = re.search(r"\{.*\}", s or "", re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}
