"""Lever postings JSON fixtures."""

from __future__ import annotations

from typing import Any

import httpx

from tests.support.httpx_mock import json_client

SITE = "acme-co"


def lever_posting(
    posting_id: str,
    *,
    title: str = "Senior Backend Engineer",
    description_plain: str = "Build Python APIs and own PostgreSQL.",
    location: str = "Remote - United States",
    workplace: str = "remote",
    commitment: str = "Full-time",
) -> dict[str, Any]:
    return {
        "id": posting_id,
        "text": title,
        "categories": {
            "commitment": commitment,
            "department": "Engineering",
            "location": location,
            "team": "Platform",
            "level": "Senior",
        },
        "descriptionPlain": description_plain,
        "description": f"<p>{description_plain}</p>",
        "lists": [{"text": "Requirements", "content": "<li>Python</li><li>PostgreSQL</li>"}],
        "hostedUrl": f"https://jobs.lever.co/{SITE}/{posting_id}",
        "applyUrl": f"https://jobs.lever.co/{SITE}/{posting_id}/apply",
        "createdAt": 1693526400000,
        "workplaceType": workplace,
    }


def lever_client(responses: dict[str, httpx.Response | list[httpx.Response]]) -> httpx.Client:
    return json_client(responses)
