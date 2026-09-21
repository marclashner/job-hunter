"""Backfill salary and eligible countries on stored jobs."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.agents.compensation_extraction import OpenAICompensationExtractor
from app.config import get_settings
from app.db import Database
from app.models.enums import EmploymentType, JobSource, RemotePolicy, Seniority
from app.models.job import Job
from app.schemas.job import JobCreate
from app.services.listing_enrichment import enrich_job_create


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse salary and eligible countries on jobs.")
    parser.add_argument("--no-llm", action="store_true", help="Regex/geo only; skip OpenAI.")
    args = parser.parse_args(argv)

    extractor = None
    if not args.no_llm:
        if not get_settings().openai_api_key:
            print("OPENAI_API_KEY is not set; using regex only.", file=sys.stderr)
        else:
            extractor = OpenAICompensationExtractor()

    database = Database(get_settings())
    session = database.session_factory()
    parsed = 0
    geos = 0
    llm_used = 0
    try:
        jobs = list(session.scalars(select(Job).order_by(Job.discovered_at.desc())).all())
        for job in jobs:
            payload = JobCreate(
                source=JobSource(job.source),
                source_job_id=job.source_job_id,
                company=job.company,
                title=job.title,
                description=job.description,
                location=job.location,
                remote_policy=RemotePolicy(job.remote_policy) if job.remote_policy else None,
                employment_type=EmploymentType(job.employment_type)
                if job.employment_type
                else None,
                seniority=Seniority(job.seniority) if job.seniority else None,
                salary_min=None,
                salary_max=None,
                salary_currency=None,
                job_url=job.job_url,
                application_url=job.application_url,
                department=job.department,
                posted_at=job.posted_at,
                discovered_at=job.discovered_at,
                raw_data=dict(job.raw_data or {}),
            )
            enriched = enrich_job_create(payload, extractor=extractor)
            job.salary_min = enriched.salary_min
            job.salary_max = enriched.salary_max
            job.salary_currency = enriched.salary_currency
            job.salary_source = enriched.salary_source.value if enriched.salary_source else None
            job.salary_quote = enriched.salary_quote
            job.eligible_countries = list(enriched.eligible_countries)
            if job.salary_min is not None or job.salary_max is not None:
                parsed += 1
                if job.salary_source == "llm":
                    llm_used += 1
            if job.eligible_countries:
                geos += 1
        session.commit()
    except Exception as exc:
        session.rollback()
        print(f"enrich failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
        database.dispose()

    print(f"jobs={len(jobs)} salary_parsed={parsed} llm={llm_used} with_geo={geos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
