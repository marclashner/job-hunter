# Replacing seed candidate data

This directory is the **only** place you should edit to swap the placeholder engineer for a real person.

1. Edit `profile.json` and `evidence.json`.
2. Mark every profile field in `field_grounding` as `evidence_backed`, `derived`, or `unknown`.
3. Cite `evidence_keys` that exist in `evidence.json`.
4. For `unknown`, omit a value (or leave it null) and do not cite evidence.
5. Reload the database:

```bash
uv run python scripts/seed_candidate.py
```

Do not encode ungrounded experience in summaries, cover letters, or agent prompts. If you cannot point at an evidence record, the field is unknown.

See `docs/candidate-evidence.md`.
