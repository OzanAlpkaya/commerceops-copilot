from collections.abc import Callable

import pytest

from mock_api.config import Settings, parse_latency

Headers = Callable[..., dict[str, str]]


def test_flags_are_off_by_default() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.latency_range == (0.0, 0.0)
    assert settings.error_rate == 0.0


def test_error_rate_one_fails_every_request(make_client, headers: Headers) -> None:
    client = make_client(error_rate=1.0)
    for _ in range(10):
        response = client.get("/orders/LH-1000001", headers=headers())
        assert response.status_code in (500, 502, 503)
        assert "code" in response.json()["error"]
    assert client.get("/health").status_code == 200


def test_latency_sleeps_within_the_range(make_client, headers: Headers, monkeypatch) -> None:
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr("mock_api.chaos.asyncio.sleep", fake_sleep)
    client = make_client(latency_ms="50-400")
    for _ in range(5):
        assert client.get("/orders/LH-1000001", headers=headers()).status_code == 200
    client.get("/health")

    assert len(delays) == 5
    assert all(0.05 <= d <= 0.4 for d in delays)


def test_no_middleware_when_flags_are_off(client, headers: Headers, monkeypatch) -> None:
    async def fail(_: float) -> None:
        raise AssertionError("slept with latency off")

    monkeypatch.setattr("mock_api.chaos.asyncio.sleep", fail)
    assert client.get("/orders/LH-1000001", headers=headers()).status_code == 200


def test_latency_parsing() -> None:
    assert parse_latency("0") == (0, 0)
    assert parse_latency("250") == (0.25, 0.25)
    assert parse_latency("50-400") == (0.05, 0.4)
    for bad in ("fast", "400-50", "-5"):
        with pytest.raises(ValueError):
            parse_latency(bad)
