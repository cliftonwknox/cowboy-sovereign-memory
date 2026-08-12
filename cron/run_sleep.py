#!/usr/bin/env python3
"""Nightly entrypoint — run the sleep cycle, then export the markdown backup.

Idempotent and safe to re-run. Wire this to run once a night (see scripts/ for systemd
timer / launchd plist / cron). On the Lite tier it simply skips the cognitive stages.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _db_creds() -> dict:
    """DB connection params — the same CCSM_DB_* the store reads, falling back to
    the repo .env file (the cron service doesn't export them)."""
    keys = {"host": "CCSM_DB_HOST", "user": "CCSM_DB_USER",
            "password": "CCSM_DB_PASSWORD", "name": "CCSM_DB_NAME"}
    creds = {k: os.environ.get(v, "") for k, v in keys.items()}
    if not creds["password"]:
        try:
            with open(os.path.join(ROOT, ".env")) as f:
                vals = dict(line.strip().split("=", 1) for line in f
                            if "=" in line and not line.lstrip().startswith("#"))
            creds = {k: creds[k] or vals.get(v, "") for k, v in keys.items()}
        except OSError:
            pass
    return creds


def backup_db_to_vault(keep: int = 14) -> str:
    """After dreaming, dump the DB to the Vault disk (gzipped, last `keep` nights).
    Best-effort; skips cleanly when the Vault isn't mounted."""
    import datetime
    import glob
    import gzip
    import subprocess

    # Which disk holds the backups is machine-specific, so it is configured rather than
    # assumed; unset means there is nowhere to put them and the step is skipped.
    vault = os.environ.get("CCSM_BACKUP_VAULT", "")
    if not vault:
        return "no backup vault configured — db backup skipped"
    if not os.path.ismount(vault):
        return "vault not mounted — db backup skipped"
    c = _db_creds()
    dest = os.path.join(vault, "cowboy-memory-backups")
    os.makedirs(dest, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    out = os.path.join(dest, f"cowboy_memory-{stamp}.sql.gz")
    # Capture then compress in Python — subprocess stdout=fh would write to the
    # raw fd and bypass the gzip wrapper (corrupt file).
    dump = subprocess.run(
        ["mariadb-dump", "-h", c["host"], "-u", c["user"],
         "--single-transaction", c["name"]],
        env={**os.environ, "MYSQL_PWD": c["password"]},
        stdout=subprocess.PIPE, check=True,
    )
    with gzip.open(out, "wb") as fh:
        fh.write(dump.stdout)
    for old in sorted(glob.glob(os.path.join(dest, "cowboy_memory-*.sql.gz")))[:-keep]:
        os.remove(old)
    return f"db backup -> {out}"


def main() -> None:
    from memory.sleep import run
    print(run())
    try:
        from backup.export_markdown import export
        n = export(os.path.join(ROOT, "backup", "markdown"))
        print(f"exported {n}")
    except Exception as e:  # backup is best-effort; never fail the cron
        print(f"backup warning: {e}")
    try:
        print(backup_db_to_vault())
    except Exception as e:  # best-effort; never fail the cron
        print(f"db backup warning: {e}")


if __name__ == "__main__":
    main()
