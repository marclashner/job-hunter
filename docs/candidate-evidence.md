# Candidate evidence and agent usage

The candidate subsystem exists so job-evaluation and application-writing agents have a **closed world** of facts. If a statement is not in `CandidateEvidence`, it is not a usable experience claim.

## Three kinds of information

Every field on `GET /candidate/profile` is a `GroundedValue`:

| `provenance` | Meaning | Agent rule |
| --- | --- | --- |
| `evidence_backed` | The `value` is supported by one or more evidence rows (`evidence_ids`) | Treat as a fact. Quote or paraphrase the cited claims. Do not strengthen them. |
| `derived` | The `value` is an interpretation of cited evidence | Use only as a summary. `interpretation_notes` explains how it was derived. Do not turn it into new skills. |
| `unknown` | `value` is always `null` | Do not fill the gap. Do not infer from job descriptions, stereotypes, or similar résumés. |

`GET /candidate/evidence` returns the atomic claims: `category`, `claim`, `detailed_description`, `technologies`, `measurable_outcomes`, `source`, `confidence`, and `tags`.

## What agents may do

- Match a job's requirements against **evidence-backed** claims and **derived** summaries that cite those claims.
- Say a requirement is **unverified** when it falls in `unknown_fields` or `unknown_categories`.
- Generate application language that stays within cited claims and measurable outcomes.

## What agents must not do

- Invent employers, titles, stack items, metrics, or domain experience.
- Treat missing frontend (or any missing category) as “the candidate is bad at it” or as “the candidate has it but forgot to say.”
- Use compensation, location, or title **preferences** as proof of skill. Those are self-reported goals (`category: self_reported`).

## Replacing the placeholder person

Seed data is a generic senior engineer named Jordan Hale, tagged `placeholder-seed`. Replace it by editing `data/candidate/profile.json` and `data/candidate/evidence.json`, then:

```bash
uv run python scripts/seed_candidate.py
```

The seed loader validates provenance rules before commit. `evidence_backed` fields need evidence keys; `derived` fields need notes and cited keys; `unknown` fields cannot carry a value.

## API

- `GET /candidate/profile` — grounded profile for the `primary` key
- `GET /candidate/evidence` — all evidence; optional `?category=`
