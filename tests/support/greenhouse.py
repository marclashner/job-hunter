"""Greenhouse Job Board JSON fixtures and httpx mock transport."""

from __future__ import annotations

from typing import Any

import httpx

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


def mock_transport(
    responses: dict[str, httpx.Response | list[httpx.Response]],
) -> httpx.MockTransport:
    queues: dict[str, list[httpx.Response]] = {}
    for key, value in responses.items():
        queues[key] = value if isinstance(value, list) else [value]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        queue = queues.get(path)
        if not queue:
            return httpx.Response(404, json={"message": "not found"})
        if len(queue) == 1:
            return queue[0]
        return queue.pop(0)

    return httpx.MockTransport(handler)


def greenhouse_client(responses: dict[str, httpx.Response | list[httpx.Response]]) -> httpx.Client:
    return httpx.Client(
        transport=mock_transport(responses),
        timeout=httpx.Timeout(2.0),
        headers={"Accept": "application/json"},
    )
