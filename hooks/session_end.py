#!/usr/bin/env python3
"""SessionEnd hook — fire end-of-session extraction, DETACHED, so it never delays close.

No-ops on the Lite tier (no dreamer configured). Reads the transcript path from the
hook payload and launches `memory.extract_session` in the background.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    transcript = data.get("transcript_path") or data.get("transcript")
    if not transcript or not os.path.exists(transcript):
        return
    try:
        from memory.config import load
        if not load().has_dreamer:
            return                                      # Lite tier
    except Exception:
        return
    try:
        subprocess.Popen(
            [sys.executable, "-m", "memory.extract_session", transcript],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except Exception:
        return


if __name__ == "__main__":
    main()
