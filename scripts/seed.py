#!/usr/bin/env python3
"""Seed the store from the human's own markdown notes. Local only — nothing transmitted.

Splits on markdown headings (one memory per section); the heading becomes the summary.
Usage:  .venv/bin/python scripts/seed.py NOTES.md [more.md ...]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.capture import remember  # noqa: E402


def seed_file(path: str) -> int:
    text = open(path, "r", errors="ignore").read()
    blocks = re.split(r"\n(?=#{1,3}\s)", text)
    n = 0
    for b in blocks:
        b = b.strip()
        if len(b) < 20:
            continue
        summary = b.splitlines()[0].lstrip("#").strip() or b[:120]
        remember(summary=summary[:200], content=b, origin="user")
        n += 1
    return n


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: seed.py NOTES.md [more.md ...]"); sys.exit(1)
    total = sum(seed_file(p) for p in sys.argv[1:])
    print(f"seeded {total} memories")
