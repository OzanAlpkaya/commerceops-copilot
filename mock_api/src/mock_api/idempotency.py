"""Idempotency keys for POST /returns.

The first successful response for (client, key) is stored. Replaying the same key with
the same body returns that response again; the same key with a different body is
rejected. Failed requests are not stored, so a key can be retried after a fix.
"""

import hashlib
import json
from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mock_api.errors import ApiError
from mock_api.models import IdempotencyKey

MAX_KEY_LENGTH = 255
REPLAY_HEADER = "Idempotent-Replayed"


def require_key(key: str | None) -> str:
    if key is None or not key.strip():
        raise ApiError(400, "idempotency_key_required", "The Idempotency-Key header is required.")
    if len(key) > MAX_KEY_LENGTH:
        raise ApiError(
            400, "idempotency_key_invalid", f"Idempotency-Key is longer than {MAX_KEY_LENGTH}."
        )
    return key


def request_hash(body: BaseModel) -> str:
    canonical = json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def replay(session: Session, client: str, key: str, body_hash: str) -> JSONResponse | None:
    """The stored response for (client, key), or None if the key is new."""
    stored = session.get(IdempotencyKey, (client, key))
    if stored is None:
        return None
    if stored.request_hash != body_hash:
        raise ApiError(
            422,
            "idempotency_key_reused",
            "This Idempotency-Key was already used with a different request body.",
        )
    return stored_response(stored)


def stored_response(stored: IdempotencyKey) -> JSONResponse:
    body: dict[str, Any] = stored.response_body
    return JSONResponse(
        body,
        status_code=stored.response_status,
        headers={REPLAY_HEADER: "true", "Location": f"/returns/{body['id']}"},
    )
