"""httpx MockTransport keyed by URL path."""

from __future__ import annotations

import httpx


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


def json_client(responses: dict[str, httpx.Response | list[httpx.Response]]) -> httpx.Client:
    return httpx.Client(
        transport=mock_transport(responses),
        timeout=httpx.Timeout(2.0),
        headers={"Accept": "application/json"},
    )
