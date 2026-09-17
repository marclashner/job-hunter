"""Health service unit tests."""

from app.services.health import check_health


class _OkSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        return None


class _FailingSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("connection refused")


def test_check_health_ok() -> None:
    result = check_health(_OkSession())  # type: ignore[arg-type]
    assert result.status == "ok"
    assert result.database == "connected"


def test_check_health_disconnected() -> None:
    result = check_health(_FailingSession())  # type: ignore[arg-type]
    assert result.status == "degraded"
    assert result.database == "disconnected"
