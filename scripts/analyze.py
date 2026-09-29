#!/usr/bin/env /usr/bin/python3
"""For each pending article past the merge grace window and not yet delivered,
pick the best-available PDF (zh > bilingual > en), extract its text, build a
prompt, and call Codex CLI to get a structured summary JSON.

Writes $RUN_DIR/reports/<key>.json (Codex output) and $RUN_DIR/ready.json
(list of keys this run produced, for validate/render/deliver to pick up).
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DIR, all_pending_keys, is_delivered, load_pending  # noqa: E402

MODEL = os.environ.get("MODEL", "gpt-5.6-terra")
MERGE_WINDOW_MINUTES = int(os.environ.get("MERGE_WINDOW_MINUTES", "15"))
MAX_BODY_CHARS = 12000

LANG_PRIORITY = ["zh", "bilingual", "en", "unknown"]


def pick_attachment(attachments):
    by_lang = {}
    for att in attachments:
        by_lang.setdefault(att["lang"], att)
    for lang in LANG_PRIORITY:
        if lang in by_lang:
            return by_lang[lang]
    return None


def extract_text(pdf_path: str) -> str:
    import fitz  # PyMuPDF, available in /usr/bin/python3 on this machine

    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text.strip()


def ready_for_analysis(record) -> bool:
    first_seen = datetime.fromisoformat(record["first_seen"])
    age_minutes = (datetime.now(timezone.utc) - first_seen).total_seconds() / 60
    return age_minutes >= MERGE_WINDOW_MINUTES and bool(record["attachments"])


def build_prompt(record, attachment, body_text: str) -> str:
    template = (DIR / "prompts" / "summarize.md").read_text(encoding="utf-8")
    body_text = body_text[:MAX_BODY_CHARS]
    return (
        template.replace("{{SOURCE}}", record["source"] or "")
        .replace("{{TITLE}}", record["title"] or "")
        .replace("{{AUTHOR}}", record["author"] or "")
        .replace("{{LANGUAGE}}", attachment["lang"])
        .replace("{{BODY_TEXT}}", body_text)
    )


def run_codex(prompt_path: Path, output_path: Path, run_dir: Path, key: str):
    stdout_log = run_dir / f"codex-{key}.stdout.log"
    stderr_log = run_dir / f"codex-{key}.stderr.log"
    with open(prompt_path, "rb") as stdin_f, open(stdout_log, "w") as out_f, open(stderr_log, "w") as err_f:
        subprocess.run(
            [
                "codex", "--ask-for-approval", "never", "exec",
                "--model", MODEL, "--sandbox", "read-only", "--cd", str(DIR), "--ephemeral",
                "--output-schema", str(DIR / "config" / "summary.schema.json"),
                "--output-last-message", str(output_path),
                "-",
            ],
            stdin=stdin_f, stdout=out_f, stderr=err_f, check=True,
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    reports_dir = run_dir / "reports"
    prompts_dir = run_dir / "prompts"
    reports_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    ready_keys = []
    for key in all_pending_keys():
        if is_delivered(key):
            continue
        record = load_pending(key)
        if not record or not ready_for_analysis(record):
            continue
        attachment = pick_attachment(record["attachments"])
        if attachment is None:
            continue
        body_text = extract_text(attachment["path"])
        if not body_text:
            print(f"WARN: empty extracted text for {key}, skipping this run", file=sys.stderr)
            continue
        prompt_path = prompts_dir / f"{key}.md"
        prompt_path.write_text(build_prompt(record, attachment, body_text), encoding="utf-8")
        output_path = reports_dir / f"{key}.json"
        run_codex(prompt_path, output_path, run_dir, key)
        ready_keys.append(key)

    (run_dir / "ready.json").write_text(json.dumps(ready_keys, ensure_ascii=False), encoding="utf-8")
    print(f"ANALYZED ready={len(ready_keys)}")


if __name__ == "__main__":
    main()
