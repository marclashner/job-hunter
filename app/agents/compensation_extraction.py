"""Optional LLM compensation extract when regex is missing or ambiguous."""

from __future__ import annotations

import json
import os
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from agents import Agent, ModelSettings, Runner, set_tracing_disabled
from app.agents.job_evaluation import EvaluationAgentError, EvaluationConfigurationError
from app.config import Settings, get_settings
from app.sources.compensation import ParsedCompensation

set_tracing_disabled(True)

INSTRUCTIONS = """
Extract the primary cash compensation range for this job posting.
Return numbers as annual USD-equivalent integers when the posting is in USD.
If the posting uses CAD, GBP, or EUR, keep that currency ISO code.
If several geo bands exist, prefer the United States / standard U.S. cost-of-living band.
Do not invent a range. If none is stated, leave min and max null and set ambiguous true.
Quote the exact phrase you used.
""".strip()


class CompensationExtraction(BaseModel):
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    period: Literal["year", "month", "hour"] = "year"
    quote: str = ""
    ambiguous: bool = False
    confidence: Literal["high", "medium", "low"] = "low"


class CompensationExtractor(Protocol):
    def extract(
        self, *, title: str, location: str | None, description: str
    ) -> ParsedCompensation | None: ...


class OpenAICompensationExtractor:
    def extract(
        self, *, title: str, location: str | None, description: str
    ) -> ParsedCompensation | None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise EvaluationConfigurationError("OPENAI_API_KEY is not set.")
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        agent = Agent(
            name="CompensationExtractor",
            instructions=INSTRUCTIONS,
            model=settings.openai_model,
            model_settings=ModelSettings(
                temperature=settings.openai_evaluation_temperature,
                top_p=1.0,
            ),
            output_type=CompensationExtraction,
        )
        payload = json.dumps(
            {
                "title": title,
                "location": location,
                "description": description[:12000],
            },
            ensure_ascii=False,
        )
        try:
            result = Runner.run_sync(agent, payload, max_turns=1)
        except Exception as exc:
            raise EvaluationAgentError("CompensationExtractor run failed") from exc
        output = result.final_output
        extraction = (
            output
            if isinstance(output, CompensationExtraction)
            else CompensationExtraction.model_validate(output)
        )
        return _to_parsed(extraction, settings)


def _to_parsed(extraction: CompensationExtraction, settings: Settings) -> ParsedCompensation | None:
    del settings
    if extraction.ambiguous or extraction.confidence == "low":
        if extraction.salary_min is None and extraction.salary_max is None:
            return None
    minimum = extraction.salary_min
    maximum = extraction.salary_max
    if extraction.period == "hour":
        minimum = None if minimum is None else minimum * 2080
        maximum = None if maximum is None else maximum * 2080
    elif extraction.period == "month":
        minimum = None if minimum is None else minimum * 12
        maximum = None if maximum is None else maximum * 12
    if minimum is None and maximum is None:
        return None
    currency = (extraction.salary_currency or "USD").upper()
    return ParsedCompensation(
        salary_min=minimum,
        salary_max=maximum,
        salary_currency=currency,
        quote=(extraction.quote or "")[:500],
        ambiguous=extraction.ambiguous,
        needs_llm=False,
    )
