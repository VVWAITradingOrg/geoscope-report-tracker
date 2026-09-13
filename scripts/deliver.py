#!/usr/bin/env /usr/bin/python3
"""Deliver rendered Discord chunks through OpenClaw transport only, then mark
each article delivered so it is never re-sent on a later run."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import mark_delivered  # noqa: E402


def send_chunk(account: str, channel: str, text: str):
    subprocess.run(
        ["openclaw", "message", "send", "--channel", "discord", "--account", account, "--target", channel, "--message", text],
        check=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--account", required=True)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        print("DELIVERED keys=0 (nothing rendered this run)")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = run_dir.name

    delivered = 0
    for key, info in manifest.items():
        chunk_dir = run_dir / "discord" / key
        chunks = sorted(chunk_dir.glob("*.txt"), key=lambda p: p.name)
        if not chunks:
            print(f"WARN: no rendered chunks for {key}, skipping", file=sys.stderr)
            continue
        for chunk in chunks:
            send_chunk(args.account, info["channel"], chunk.read_text(encoding="utf-8").strip())
        mark_delivered(key, run_id)
        delivered += 1

    print(f"DELIVERED keys={delivered}")


if __name__ == "__main__":
    main()
