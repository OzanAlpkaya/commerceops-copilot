"""Realism flags: added latency and random 5xx responses. Both are off by default."""

import asyncio
import random
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from mock_api.errors import error_body

EXEMPT_PATHS = frozenset({"/health"})
FAILURES = (
    (500, "internal_error", "Internal server error."),
    (502, "bad_gateway", "Upstream service unavailable."),
    (503, "service_unavailable", "Service temporarily unavailable."),
)


def install_chaos(
    app: FastAPI, latency: tuple[float, float], error_rate: float, rng: random.Random
) -> None:
    low, high = latency
    if high == 0 and error_rate == 0:
        return

    @app.middleware("http")
    async def chaos(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        if high > 0:
            await asyncio.sleep(rng.uniform(low, high))
        if error_rate > 0 and rng.random() < error_rate:
            status, code, message = rng.choice(FAILURES)
            return JSONResponse(error_body(code, message), status_code=status)
        return await call_next(request)
