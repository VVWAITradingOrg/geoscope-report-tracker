#!/usr/bin/env /usr/bin/python3
"""Render each validated report into a Discord-safe text chunk under
$RUN_DIR/discord/<key>/01.txt, tagged with the target channel from
config/sources.json."""
import argparse
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
LIMIT = 1850

STANCE_EMOJI = {"bullish": "🟢多", "bearish": "🔴空", "neutral": "⚪中性"}


def render_text(key: str, data: dict, record: dict) -> str:
    lines = [f"**{data['title']}**", f"来源：{data['source']} · 作者：{data['author']} · 摘要语言：{data['language_used']}", ""]
    lines.append("核心观点：")
    for i, point in enumerate(data["core_points"], 1):
        lines.append(f"{i}. {point}")
    tickers = data.get("tickers", [])
    if tickers:
        lines.append("")
        lines.append("标的：")
        for t in tickers:
            emoji = STANCE_EMOJI.get(t["stance"], t["stance"])
            lines.append(f"- {t['name']} [{emoji}]：{t['reason']}")
    links = [u for u in (record.get("source_url"), record.get("geoscope_url")) if u]
    if links:
        lines.append("")
        lines.append(" | ".join(links))
    return "\n".join(lines).strip()


def split_chunks(text: str) -> list:
    if len(text) <= LIMIT:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= LIMIT:
            current = candidate
        else:
            chunks.append(current)
            current = line
    if current:
        chunks.append(current)
    total = len(chunks)
    return [f"{c}\n({i}/{total})" for i, c in enumerate(chunks, 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    ready = json.loads((run_dir / "ready.json").read_text(encoding="utf-8"))
    sources = json.loads((DIR / "config" / "sources.json").read_text(encoding="utf-8"))

    manifest = {}
    for key in ready:
        data = json.loads((run_dir / "reports" / f"{key}.json").read_text(encoding="utf-8"))
        record = json.loads((DIR / "state" / "pending" / f"{key}.json").read_text(encoding="utf-8"))
        channel = sources.get(record["source"], {}).get("channel")
        if not channel:
            raise SystemExit(f"no Discord channel configured for source {record['source']!r} (key={key}); add it to config/sources.json")
        text = render_text(key, data, record)
        chunk_dir = run_dir / "discord" / key
        chunk_dir.mkdir(parents=True, exist_ok=True)
        for i, chunk in enumerate(split_chunks(text), 1):
            (chunk_dir / f"{i:02d}.txt").write_text(chunk + "\n", encoding="utf-8")
        manifest[key] = {"channel": channel}

    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"RENDERED keys={len(manifest)}")


if __name__ == "__main__":
    main()
