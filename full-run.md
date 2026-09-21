# Full run — live Greenhouse/Lever ingest + OpenAI evaluation

Run date: 2026-09-21. Working directory: `/Users/marclashner/Development/job-hunter`.

Dashboard: http://127.0.0.1:8000/

Outcome after this run:

| Metric | Value |
| --- | --- |
| Jobs kept for review | 100 (pruned from 2,865 synced listings) |
| Evaluated and on the dashboard | 90 |
| Recommended apply | 22 |
| Needing review | 28 |
| Reject (including hard-filter discards) | 40 |
| Unevaluated (agent grounding still failing) | 10 |

The configured database is `DATABASE_URL` on `localhost:5433`. Application tables were truncated; Docker Compose was not used to wipe data because port 5433 is not the Compose Postgres listener.

---

## 1. Preconditions

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('/Users/marclashner/Development/job-hunter/.env')
text = p.read_text() if p.exists() else ''
has_key = any(
    line.startswith('OPENAI_API_KEY=')
    and len(line.strip().split('=', 1)[-1].strip().strip('"')) > 8
    for line in text.splitlines()
    if not line.startswith('#')
)
print('env_file_exists', p.exists())
print('openai_key_configured', has_key)
PY
```

```bash
docker compose ps
```

```bash
python3 - <<'PY'
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error

green = [
    "stripe","openai","anthropic","gitlab","notion","figma","cloudflare","plaid","databricks",
    "huggingface","vercel","twilio","benchling","abridge","omadahealth","cityblockhealth",
    "includedhealth","springhealth","headway","headwayco","cedar","withcedar","goodrx","natera",
    "tempus","collectivehealth","dandy","joindandy","ramp","mercury","gusto","airbyte","dbtlabs",
    "fivetran","grafana","hashicorp","docker","reddit","dropbox","intercom","elastic","color",
    "modernhealth","transcarent","commure","innovaccer","suki","noom","hims","oscarhealth",
    "oscar","wellframe","airbnb","discord","shopify","canonical","sentry","datadog","okta",
    "auth0","confluent","snowflake","mongodb","elasticco","elasticpath","grafana-labs",
    "grafanalabs","temporal","temporalio","temporaltechnologies","langchain","anyscale",
    "togetherai","together","cohere","scaleai","scale","weightsandbiases","wandb",
    "retool","linear","linearapp","rampdotcom","anduril","andurilindustries",
    "cigna","unitedhealth","optum","changehealthcare","flatironhealth","flatiron","tempustech",
    "tempuslabs","tempusai","colorhealth","colorgenomics",
    "omada","omadahealthinc","lyrahealth","lyra","springhealthinc","includedhealthinc",
    "cityblock","cedarinc","cedarcare","goodrxinc","dandydental","dandy",
    "collectivehealthinc","healthopx","breathe","breathesuite"
]
lever = [
    "palantir","canva","netflix","shopify","reddit","figma","notion","airbnb","discord",
    "anduril","andurilindustries","ramp","mercury","plaid","stripe","openai","anthropic",
    "benchling","abridge","omada","omadahealth","cityblock","cityblockhealth","includedhealth",
    "springhealth","headway","cedar","goodrx","natera","tempus","collectivehealth","dandy",
    "lyra","lyrahealth","modernhealth","transcarent","commure","suki","noom","hims",
    "wellframe","airbyte","dbt","dbtlabs","fivetran","grafana","hashicorp","docker",
    "dropbox","intercom","elastic","sentry","okta","snowflake","mongodb","temporal",
    "langchain","anyscale","together","cohere","scaleai","wandb","retool","linear",
    "canonical","gitlab","cloudflare","twilio","databricks","huggingface","vercel",
    "gusto","confluent","auth0","datadog","oscar","oscarhealth","color","colorhealth"
]

def gh(token):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            data = json.load(r)
        jobs = data.get("jobs") if isinstance(data, dict) else None
        n = len(jobs) if isinstance(jobs, list) else -1
        return ("greenhouse", token, 200, n)
    except urllib.error.HTTPError as e:
        return ("greenhouse", token, e.code, 0)
    except Exception as e:
        return ("greenhouse", token, str(e.__class__.__name__), 0)

def lv(site):
    url = f"https://api.lever.co/v0/postings/{site}?mode=json&limit=1"
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            data = json.load(r)
        return ("lever", site, 200, "ok" if isinstance(data, list) else "bad")
    except urllib.error.HTTPError as e:
        return ("lever", site, e.code, 0)
    except Exception as e:
        return ("lever", site, str(e.__class__.__name__), 0)

ok_g = []
ok_l = []
with ThreadPoolExecutor(max_workers=16) as ex:
    futs = [ex.submit(gh, t) for t in dict.fromkeys(green)] + [
        ex.submit(lv, t) for t in dict.fromkeys(lever)
    ]
    for fut in as_completed(futs):
        src, ident, status, n = fut.result()
        if src == "greenhouse" and status == 200 and isinstance(n, int) and n > 0:
            ok_g.append((ident, n))
        elif src == "lever" and status == 200 and n == "ok":
            ok_l.append(ident)

print("GREENHOUSE")
for ident, n in sorted(ok_g, key=lambda x: -x[1]):
    print(f"  {ident:28} {n}")
print("LEVER")
for ident in sorted(ok_l):
    print(f"  {ident}")
print("counts", len(ok_g), len(ok_l))
PY
```

```bash
python3 - <<'PY'
import json, urllib.request
for site in ["includedhealth","lyrahealth","transcarent","palantir","anyscale"]:
    url = f"https://api.lever.co/v0/postings/{site}?mode=json&limit=100"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    print(site, len(data), 'page1')
PY
```

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN; lsof -nP -iTCP:8001 -sTCP:LISTEN; lsof -nP -iTCP:5433 -sTCP:LISTEN
```

---

## 2. Clear the database and seed the candidate

```bash
~/.local/bin/uv run python - <<'PY'
from sqlalchemy import text
from app.config import get_settings
from app.db import Database

db = Database(get_settings())
session = db.session_factory()
try:
    before = {
        row[0]: row[1]
        for row in session.execute(
            text(
                """
                SELECT 'jobs', count(*) FROM jobs
                UNION ALL SELECT 'job_evaluations', count(*) FROM job_evaluations
                UNION ALL SELECT 'candidate_profiles', count(*) FROM candidate_profiles
                UNION ALL SELECT 'candidate_evidence', count(*) FROM candidate_evidence
                """
            )
        )
    }
    print("before", before)
    session.execute(
        text(
            "TRUNCATE TABLE job_evaluations, jobs, candidate_evidence, candidate_profiles RESTART IDENTITY CASCADE"
        )
    )
    session.commit()
    after = {
        row[0]: row[1]
        for row in session.execute(
            text(
                """
                SELECT 'jobs', count(*) FROM jobs
                UNION ALL SELECT 'job_evaluations', count(*) FROM job_evaluations
                UNION ALL SELECT 'candidate_profiles', count(*) FROM candidate_profiles
                UNION ALL SELECT 'candidate_evidence', count(*) FROM candidate_evidence
                """
            )
        )
    }
    print("after", after)
finally:
    session.close()
    db.dispose()
PY
```

```bash
~/.local/bin/uv run alembic upgrade head
~/.local/bin/uv run python scripts/seed_candidate.py
```

Seed result: `key=primary`, 17 evidence records from `data/candidate`.

---

## 3. Restart the API

```bash
kill 43086 10228 10164 2>/dev/null; sleep 1
lsof -nP -iTCP:8000 -sTCP:LISTEN || true
lsof -nP -iTCP:8001 -sTCP:LISTEN || true
```

```bash
~/.local/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/candidate/profile | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["name"]["value"], "titles", d["target_titles"]["value"][:2])'
```

---

## 4. Pull live Greenhouse and Lever jobs

Boards were chosen for healthcare, healthtech, insurance, payments/fintech, and applied AI / developer tools. `transcarent` was skipped (empty Lever board).

```bash
set -euo pipefail
for token in oscar natera flatironhealth omadahealth modernhealth suki collectivehealth togetherai vercel mercury scaleai anthropic gitlab gusto; do
  echo "=== greenhouse $token ==="
  curl -sS -X POST "http://127.0.0.1:8000/sources/greenhouse/${token}/sync"
  echo
done
for site in includedhealth lyrahealth palantir anyscale; do
  echo "=== lever $site ==="
  curl -sS -X POST "http://127.0.0.1:8000/sources/lever/${site}/sync"
  echo
done
```

Sync totals (inserted):

| Source | Board | Inserted |
| --- | --- | --- |
| greenhouse | oscar | 290 |
| greenhouse | natera | 202 |
| greenhouse | flatironhealth | 27 |
| greenhouse | omadahealth | 17 |
| greenhouse | modernhealth | 13 |
| greenhouse | suki | 10 |
| greenhouse | collectivehealth | 2 |
| greenhouse | togetherai | 77 |
| greenhouse | vercel | 84 |
| greenhouse | mercury | 65 |
| greenhouse | scaleai | 222 |
| greenhouse | anthropic | 617 |
| greenhouse | gitlab | 206 |
| greenhouse | gusto | 93 |
| lever | includedhealth | 57 |
| lever | lyrahealth | 570 |
| lever | palantir | 312 |
| lever | anyscale | 1 |
| | **all boards** | **2,865** |

---

## 5. Limit to 100 relevant jobs

```bash
~/.local/bin/uv run python - <<'PY'
"""Keep the 100 most relevant jobs for Marc's search; delete the rest."""
from __future__ import annotations

import re
from sqlalchemy import func, select
from app.config import get_settings
from app.db import Database
from app.models.job import Job

KEEP = 100
POSITIVE_TITLE = re.compile(
    r"\b(software|backend|full[ -]?stack|fullstack|platform|infrastructure|"
    r"ai|ml|machine learning|llm|python|data engineer|sre|devops|swe)\b",
    re.I,
)
SENIOR = re.compile(r"\b(senior|staff|principal|founding|lead)\b", re.I)
ENGINEER = re.compile(r"\b(engineer|developer|programmer)\b", re.I)
EXCLUDE = re.compile(
    r"\b(intern|internship|junior|account executive|sales|recruiter|"
    r"registered nurse|physician|medical assistant|territory|"
    r"customer success|account manager)\b",
    re.I,
)
HEALTH = re.compile(
    r"health|clinical|hipaa|insurance|care delivery|ehr|medical",
    re.I,
)
AI = re.compile(r"\b(ai|llm|agent|machine learning|ml)\b", re.I)
STACK = re.compile(r"python|fastapi|typescript|postgresql|kubernetes", re.I)

db = Database(get_settings())
session = db.session_factory()
try:
    jobs = list(session.scalars(select(Job)).all())
    print("jobs_before", len(jobs))

    scored: list[tuple[int, Job]] = []
    for job in jobs:
        title = job.title or ""
        blob = " ".join(
            part
            for part in (job.title, job.company, job.location, job.description or "")
            if part
        )
        if EXCLUDE.search(title):
            continue
        if not ENGINEER.search(title):
            continue
        if not POSITIVE_TITLE.search(title) and not SENIOR.search(title):
            continue
        score = 0
        if SENIOR.search(title):
            score += 40
        if POSITIVE_TITLE.search(title):
            score += 25
        if job.remote_policy == "remote":
            score += 20
        elif job.remote_policy == "hybrid":
            score += 5
        if HEALTH.search(blob):
            score += 20
        if AI.search(title) or AI.search(job.company or ""):
            score += 15
        if STACK.search(blob[:4000]):
            score += 10
        if job.salary_min and job.salary_min >= 180000:
            score += 10
        scored.append((score, job))

    scored.sort(key=lambda item: (-item[0], item[1].discovered_at))
    keep_ids = {job.id for _, job in scored[:KEEP]}
    print("matching_relevant", len(scored))
    print("keeping", len(keep_ids))
    print("top_titles")
    for score, job in scored[:15]:
        print(f"  {score:3} {job.company:22} {job.remote_policy or '-':8} {job.title}")

    deleted = 0
    for job in jobs:
        if job.id not in keep_ids:
            session.delete(job)
            deleted += 1
    session.commit()
    remaining = session.scalar(select(func.count()).select_from(Job))
    print("deleted", deleted, "jobs_after", remaining)
finally:
    session.close()
    db.dispose()
PY
```

Result: 538 title-matched roles; kept the top 100; deleted 2,765.

---

## 6. Evaluate with the OpenAI agent

First batch used `concurrency: 4`. Many calls failed with an asyncio event-loop error in the Agents SDK, so remaining jobs were retried at `concurrency: 1`. Ten listings still failed evidence grounding and were not persisted (by design: failed live runs are not stored as fake scores).

```bash
curl -sS -X POST http://127.0.0.1:8000/evaluation/batch \
  -H "Content-Type: application/json" \
  -d '{"limit": 100, "evaluation_mode": "live_llm", "concurrency": 4}'
```

First-batch result: `discovered=100`, `hard_filtered=38`, `evaluated=29`, `apply=10`, `review=18`, `reject=1`, plus agent/grounding errors. Usage: 317,345 tokens, about `$0.052`.

```bash
curl -sS -X POST http://127.0.0.1:8000/evaluation/batch \
  -H "Content-Type: application/json" \
  -d '{"limit": 100, "evaluation_mode": "live_llm", "concurrency": 1}'
```

Second-batch result: `discovered=33`, `evaluated=22`, `apply=12`, `review=9`, `reject=1`, 11 grounding errors. Usage: 244,983 tokens, about `$0.040`.

```bash
curl -sS -X POST http://127.0.0.1:8000/evaluation/batch \
  -H "Content-Type: application/json" \
  -d '{"limit": 20, "evaluation_mode": "live_llm", "concurrency": 1}'
```

Third-batch result: `discovered=11`, `evaluated=1`, 10 remaining grounding errors. Usage: 11,672 tokens, about `$0.002`.

---

## 7. Confirm the dashboard

```bash
curl -sS http://127.0.0.1:8000/review/summary
curl -sS 'http://127.0.0.1:8000/review/jobs?recommendation=apply&limit=5'
curl -sS 'http://127.0.0.1:8000/review/jobs?limit=200'
```

`GET /review/summary`:

```json
{
  "discovered_today": 100,
  "evaluated": 90,
  "recommended_applications": 22,
  "needing_review": 28,
  "applications_submitted": 0,
  "interviews": 0,
  "offers": 0
}
```

Open http://127.0.0.1:8000/ and filter recommendation **Apply** to review the 22 live recommendations. Human Approve / Review / Reject still does not submit applications.
