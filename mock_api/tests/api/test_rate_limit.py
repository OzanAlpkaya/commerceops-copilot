from collections.abc import Callable

from fastapi.testclient import TestClient

from mock_api.ratelimit import SlidingWindowLimiter

Headers = Callable[..., dict[str, str]]


def test_101st_request_in_a_minute_is_429(client: TestClient, headers: Headers, clock) -> None:
    for i in range(100):
        response = client.get("/products/LUM-BED-10001", headers=headers())
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Remaining"] == str(99 - i)
        clock.advance(0.1)  # 100 requests spread over 10 seconds

    limited = client.get("/products/LUM-BED-10001", headers=headers())

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.headers["X-RateLimit-Remaining"] == "0"
    # The first request was at t=0 and the clock is at t=10: a slot frees up in 50 s.
    assert limited.headers["Retry-After"] == "50"


def test_limit_resets_after_the_window(client: TestClient, headers: Headers, clock) -> None:
    for _ in range(100):
        client.get("/products/LUM-BED-10001", headers=headers())
    assert client.get("/products/LUM-BED-10001", headers=headers()).status_code == 429

    clock.advance(60)

    assert client.get("/products/LUM-BED-10001", headers=headers()).status_code == 200


def test_each_key_has_its_own_limit(client: TestClient, headers: Headers) -> None:
    for _ in range(100):
        client.get("/products/LUM-BED-10001", headers=headers("copilot"))
    assert client.get("/products/LUM-BED-10001", headers=headers("copilot")).status_code == 429
    assert client.get("/products/LUM-BED-10001", headers=headers("admin")).status_code == 200


def test_public_and_rejected_requests_do_not_count(client: TestClient, headers: Headers) -> None:
    for _ in range(150):
        client.get("/health")
        client.get("/products/LUM-BED-10001", headers=headers("not-a-key"))
    response = client.get("/products/LUM-BED-10001", headers=headers())
    assert response.headers["X-RateLimit-Remaining"] == "99"


def test_sliding_window_frees_slots_one_by_one() -> None:
    now = [0.0]
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60, clock=lambda: now[0])
    for t in (0, 20, 40):
        now[0] = t
        assert limiter.hit("k").allowed
    now[0] = 59
    assert limiter.hit("k").retry_after == 1
    now[0] = 60  # the t=0 request has left the window
    assert limiter.hit("k").allowed
    assert not limiter.hit("k").allowed
