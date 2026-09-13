#!/usr/bin/env /usr/bin/python3
"""Semantic validation of each ready report beyond what --output-schema enforces.
Any failure here aborts the whole pipeline run (no partial delivery of unvalidated content).
"""
import argparse
import json
import sys
from pathlib import Path

STANCES = {"bullish", "bearish", "neutral"}
LANGUAGES = {"zh", "bilingual", "en"}


def validate_one(key: str, data: dict) -> list:
    errors = []
    for field in ("title", "source", "author", "language_used", "core_points", "tickers"):
        if field not in data:
            errors.append(f"{key}: missing field {field}")
    if "language_used" in data and data["language_used"] not in LANGUAGES:
        errors.append(f"{key}: invalid language_used {data.get('language_used')!r}")
    points = data.get("core_points", [])
    if not (3 <= len(points) <= 5):
        errors.append(f"{key}: core_points has {len(points)} items, expected 3-5")
    for i, p in enumerate(points):
        if not isinstance(p, str) or not p.strip():
            errors.append(f"{key}: core_points[{i}] is empty")
    for i, ticker in enumerate(data.get("tickers", [])):
        for field in ("name", "stance", "reason"):
            if not ticker.get(field):
                errors.append(f"{key}: tickers[{i}] missing {field}")
        if ticker.get("stance") not in STANCES:
            errors.append(f"{key}: tickers[{i}] invalid stance {ticker.get('stance')!r}")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    ready = json.loads((run_dir / "ready.json").read_text(encoding="utf-8"))

    all_errors = []
    for key in ready:
        report_path = run_dir / "reports" / f"{key}.json"
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            all_errors.append(f"{key}: could not read/parse report: {exc}")
            continue
        all_errors.extend(validate_one(key, data))

    if all_errors:
        for err in all_errors:
            print(f"INVALID: {err}", file=sys.stderr)
        return 1
    print(f"VALID reports={len(ready)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
