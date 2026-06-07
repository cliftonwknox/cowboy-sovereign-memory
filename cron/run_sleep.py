#!/usr/bin/env python3
"""Nightly entrypoint — run the sleep cycle, then export the markdown backup.

Idempotent and safe to re-run. Wire this to run once a night (see scripts/ for systemd
timer / launchd plist / cron). On the Lite tier it simply skips the cognitive stages.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> None:
    from memory.sleep import run
    print(run())
    try:
        from backup.export_markdown import export
        n = export(os.path.join(ROOT, "backup", "markdown"))
        print(f"exported {n}")
    except Exception as e:  # backup is best-effort; never fail the cron
        print(f"backup warning: {e}")


if __name__ == "__main__":
    main()
