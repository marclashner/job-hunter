"""Fill salary and eligible countries after board normalization."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.compensation_extraction import CompensationExtractor
from app.agents.job_evaluation import EvaluationAgentError, EvaluationConfigurationError
from app.models.enums import SalarySource
from app.schemas.job import JobCreate
from app.sources.compensation import compensation_from_metadata, parse_compensation
from app.sources.geo import parse_eligible_countries

logger = logging.getLogger(__name__)


def enrich_job_create(
    payload: JobCreate,
    *,
    extractor: CompensationExtractor | None = None,
) -> JobCreate:
    countries = list(payload.eligible_countries) or parse_eligible_countries(payload.location)
    salary_min = payload.salary_min
    salary_max = payload.salary_max
    salary_currency = payload.salary_currency
    salary_source = payload.salary_source
    salary_quote = payload.salary_quote

    if salary_min is not None or salary_max is not None:
        if salary_source is None:
            salary_source = SalarySource.STRUCTURED_API
    else:
        parsed = compensation_from_metadata(_metadata(payload.raw_data))
        if parsed is None or (parsed.salary_min is None and parsed.salary_max is None):
            parsed = parse_compensation(payload.description, payload.title)
        used_llm = False
        if parsed is None or parsed.needs_llm or parsed.ambiguous:
            if extractor is not None:
                try:
                    llm = extractor.extract(
                        title=payload.title,
                        location=payload.location,
                        description=payload.description,
                    )
                except (EvaluationAgentError, EvaluationConfigurationError) as exc:
                    logger.warning("Compensation LLM extract skipped: %s", exc)
                    llm = None
                if llm is not None and (llm.salary_min is not None or llm.salary_max is not None):
                    parsed = llm
                    used_llm = True
        if parsed is not None and (parsed.salary_min is not None or parsed.salary_max is not None):
            salary_min = parsed.salary_min
            salary_max = parsed.salary_max
            salary_currency = parsed.salary_currency
            salary_quote = parsed.quote or None
            salary_source = SalarySource.LLM if used_llm else SalarySource.REGEX

    return payload.model_copy(
        update={
            "eligible_countries": countries,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": salary_currency,
            "salary_source": salary_source,
            "salary_quote": salary_quote,
        }
    )


def _metadata(raw_data: dict[str, Any]) -> object:
    payload = raw_data.get("payload")
    if isinstance(payload, dict):
        return payload.get("metadata")
    return None
