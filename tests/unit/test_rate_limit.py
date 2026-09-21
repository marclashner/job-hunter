"""Unit tests for in-process API rate limiting."""

import pytest

from app.services.rate_limit import RateLimiter


def test_rate_limiter_spaces_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 0.0}
    sleeps: list[float] = []

    def monotonic() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr("app.services.rate_limit.time.monotonic", monotonic)
    monkeypatch.setattr("app.services.rate_limit.time.sleep", sleep)

    limiter = RateLimiter(per_minute=60)
    limiter.acquire()
    limiter.acquire()
    assert sleeps == [1.0]


def test_rate_limiter_disabled_when_per_minute_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_sleep(_seconds: float) -> None:
        raise AssertionError("sleep should not run")

    monkeypatch.setattr("app.services.rate_limit.time.sleep", fail_sleep)
    limiter = RateLimiter(per_minute=0)
    limiter.acquire()
    limiter.acquire()
