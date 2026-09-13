# geoscope-report-tracker

This repository is a local macOS automation project. `pipeline.sh` is the only production entrypoint.

- Summarization is executed by Codex CLI (`gpt-5.6-sol`), never by an OpenClaw agent.
- OpenClaw may only transport validated output to Discord (`openclaw message send`).
- Never place credentials in this repository. Codex reuses local CLI auth; `gog` reuses its own OAuth for Gmail; Discord delivery reuses the configured OpenClaw account.
- A failed fetch, PDF extraction, Codex call, or validation failure must stop delivery — exit non-zero, never report success after a failed step.
- Use `./pipeline.sh --no-deliver` for tests.
- Do not enable/load the LaunchAgent or send a real Discord message without explicit authorization from the user.
- New GeoScope publishers get a new Discord channel under `vvw情报分享` and a new entry in `config/sources.json` — do not default an unmapped source into an existing channel; fail loudly instead (see `scripts/render.py`).
