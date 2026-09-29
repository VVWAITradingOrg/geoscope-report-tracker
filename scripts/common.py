"""Shared helpers for the GeoScope report tracker pipeline."""
import json
import os
import subprocess
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
STATE = DIR / "state"
PENDING_DIR = STATE / "pending"
DELIVERED_DIR = STATE / "delivered"
PDFS_DIR = STATE / "pdfs"

GOG_ACCOUNT = os.environ.get("GOG_ACCOUNT", "ljianhui90@gmail.com")


def gog_json(*args):
    cmd = ["gog", "gmail", *args, "-a", GOG_ACCOUNT, "--json"]
    for attempt in range(3):
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode == 0:
            break
        if attempt == 2 or not any(reason in out.stderr for reason in
                ("rateLimitExceeded", "userRateLimitExceeded", "429 Too Many Requests")):
            break
        time.sleep(20 * (attempt + 1))
    if out.returncode != 0:
        raise RuntimeError(f"gog failed (exit={out.returncode}): {out.stderr[:300]}")
    return json.loads(out.stdout)


def load_sources():
    return json.loads((DIR / "config" / "sources.json").read_text(encoding="utf-8"))


def pending_path(key):
    return PENDING_DIR / f"{key}.json"


def delivered_path(key):
    return DELIVERED_DIR / f"{key}.json"


def load_pending(key):
    path = pending_path(key)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_pending(key, record):
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    pending_path(key).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def is_delivered(key):
    return delivered_path(key).exists()


def mark_delivered(key, run_id):
    DELIVERED_DIR.mkdir(parents=True, exist_ok=True)
    delivered_path(key).write_text(
        json.dumps({"run_id": run_id}, ensure_ascii=False), encoding="utf-8"
    )


def all_pending_keys():
    if not PENDING_DIR.exists():
        return []
    return sorted(p.stem for p in PENDING_DIR.glob("*.json"))
