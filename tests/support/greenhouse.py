"""Greenhouse Job Board JSON fixtures and httpx mock transport."""

from __future__ import annotations

from typing import Any

import httpx

from tests.support.httpx_mock import json_client, mock_transport

BOARD_TOKEN = "acme-co"


def board_payload(name: str = "Acme Co") -> dict[str, Any]:
    return {"name": name, "content": None}


def greenhouse_job(
    job_id: int,
    *,
    title: str = "Senior Backend Engineer",
    content: str = "<p>Build Python APIs and own PostgreSQL.</p>",
    location: str = "Remote - United States",
    url: str | None = None,
) -> dict[str, Any]:
    return {
        "id": job_id,
        "title": title,
        "content": content,
        "absolute_url": url or f"https://boards.greenhouse.io/{BOARD_TOKEN}/jobs/{job_id}",
        "updated_at": "2026-09-01T12:00:00Z",
        "first_published": "2026-08-15T09:00:00Z",
        "location": {"name": location},
        "departments": [{"id": 1, "name": "Engineering"}],
        "offices": [{"id": 2, "name": location}],
        "metadata": [
            {"id": 9, "name": "Employment Type", "value": "Full-time", "value_type": "text"}
        ],
    }


def greenhouse_client(responses: dict[str, httpx.Response | list[httpx.Response]]) -> httpx.Client:
    return json_client(responses)


__all__ = [
    "BOARD_TOKEN",
    "board_payload",
    "greenhouse_client",
    "greenhouse_job",
    "mock_transport",
]
