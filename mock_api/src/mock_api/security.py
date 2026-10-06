"""API key authentication, scopes and the per-client rate limit."""

import hmac
from typing import Annotated

from fastapi import Depends, Header, Request, Response

from mock_api.config import ApiClient
from mock_api.errors import ApiError
from mock_api.ratelimit import SlidingWindowLimiter


def authenticate(request: Request, x_api_key: Annotated[str | None, Header()] = None) -> ApiClient:
    """The client whose key is in X-API-Key; 401 otherwise."""
    clients: tuple[ApiClient, ...] = request.app.state.clients
    match = None
    if x_api_key:
        given = x_api_key.encode()
        # Compare against every key so timing does not reveal which one is close.
        for client in clients:
            if hmac.compare_digest(given, client.key.get_secret_value().encode()):
                match = client
    if match is None:
        raise ApiError(401, "unauthorized", "Missing or invalid X-API-Key header.")
    return match


def rate_limited_client(
    request: Request, response: Response, client: Annotated[ApiClient, Depends(authenticate)]
) -> ApiClient:
    limiter: SlidingWindowLimiter = request.app.state.limiter
    decision = limiter.hit(client.name)
    headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
    }
    if not decision.allowed:
        raise ApiError(
            429,
            "rate_limited",
            f"Rate limit of {decision.limit} requests per minute exceeded.",
            headers={**headers, "Retry-After": str(decision.retry_after)},
        )
    response.headers.update(headers)
    return client


ClientDep = Annotated[ApiClient, Depends(rate_limited_client)]


def require_scope(scope: str):
    def check(client: ClientDep) -> ApiClient:
        if scope not in client.scopes:
            raise ApiError(403, "insufficient_scope", f"This API key lacks the {scope!r} scope.")
        return client

    return check
