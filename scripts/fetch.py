#!/usr/bin/env /usr/bin/python3
"""Pull new GeoScope newsletter emails via gog, download PDF attachments, and
group them by (source, article slug) into state/pending/<key>.json.

Dedup is two-layered:
- Gmail label GMAIL_PROCESSED_LABEL marks raw messages already ingested, so a
  re-run never re-downloads the same message's attachments.
- state/pending/<source>__<slug>.json accumulates attachments across separate
  emails for the same article (e.g. an "English original" and a later
  "bilingual" email for the same piece).
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GOG_ACCOUNT, PDFS_DIR, gog_json, load_pending, save_pending  # noqa: E402

SENDER = os.environ.get("GMAIL_SENDER", "updates@mail.geoscopeapp.com")
LABEL = os.environ.get("GMAIL_PROCESSED_LABEL", "geoscope-processed")

# order matters: check longer/more specific prefixes first where they could overlap
LANG_PREFIX = [("双语", "bilingual"), ("中", "zh"), ("英", "en")]

FIELD_PATTERNS = {
    "geoscope_url": re.compile(r"查看网页版[，,][^\n]*?：(https://\S+)"),
    "source": re.compile(r"^来源：([^\n]+)", re.M),
    "title": re.compile(r"^标题：([^\n]+)", re.M),
    "author": re.compile(r"^作者：([^\n]+)", re.M),
    "source_url": re.compile(r"^链接：(https://\S+)", re.M),
}
SLUG_RE = re.compile(r"/publisher/([^/]+)/articles/(\S+)")


def parse_body(body: str):
    fields = {k: (m.group(1).strip() if (m := p.search(body)) else None) for k, p in FIELD_PATTERNS.items()}
    m = SLUG_RE.search(fields.get("geoscope_url") or "")
    fields["source_key"] = m.group(1) if m else None
    fields["slug"] = m.group(2) if m else None
    return fields


def lang_for_filename(filename: str) -> str:
    for prefix, lang in LANG_PREFIX:
        if filename.startswith(prefix):
            return lang
    return "unknown"


def ensure_label():
    labels = gog_json("labels", "list").get("labels", [])
    if not any(l.get("name") == LABEL for l in labels):
        subprocess.run(["gog", "gmail", "labels", "create", LABEL, "-a", GOG_ACCOUNT], check=True, capture_output=True)


def download_attachment(message_id: str, index: int, dest: Path):
    subprocess.run(
        [
            "gog", "gmail", "attachment", message_id, str(index),
            "-a", GOG_ACCOUNT, "--use-indexed-attachment-ids", "--out", str(dest),
        ],
        check=True, capture_output=True, text=True,
    )


def mark_processed(message_id: str):
    subprocess.run(
        ["gog", "gmail", "messages", "modify", message_id, "-a", GOG_ACCOUNT, f"--add={LABEL}"],
        check=True, capture_output=True, text=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_label()

    result = gog_json("messages", "search", f"from:{SENDER} -label:{LABEL}")
    messages = result.get("messages", [])
    fetched = 0
    for msg in messages:
        message_id = msg["id"]
        detail = gog_json("get", message_id)
        body = detail.get("body", "") or ""
        fields = parse_body(body)
        if not fields["slug"] or not fields["source_key"]:
            print(f"WARN: could not parse article slug from message {message_id}, skipping label+retry next run", file=sys.stderr)
            continue

        key = f"{fields['source_key']}__{fields['slug']}"
        record = load_pending(key) or {
            "source": fields["source"] or fields["source_key"],
            "source_key": fields["source_key"],
            "slug": fields["slug"],
            "title": fields["title"],
            "author": fields["author"],
            "geoscope_url": fields["geoscope_url"],
            "source_url": fields["source_url"],
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "attachments": [],
        }

        for idx, att in enumerate(detail.get("attachments", [])):
            filename = att.get("filename", "")
            if not filename.lower().endswith(".pdf"):
                continue
            lang = lang_for_filename(filename)
            if any(a["message_id"] == message_id and a["lang"] == lang for a in record["attachments"]):
                continue
            dest = PDFS_DIR / f"{message_id}-{idx}.pdf"
            download_attachment(message_id, idx, dest)
            record["attachments"].append({"lang": lang, "path": str(dest), "message_id": message_id})

        save_pending(key, record)
        mark_processed(message_id)
        fetched += 1

    print(f"FETCHED messages={fetched}")


if __name__ == "__main__":
    main()
