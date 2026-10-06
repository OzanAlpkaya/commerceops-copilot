"""Opaque-cursor (keyset) pagination for list endpoints.

The cursor is base64url-encoded JSON holding the sort key of the last row returned.
Clients treat it as opaque; rows inserted during a walk never cause duplicates.
"""

import base64
import binascii
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import Query
from sqlalchemy import Select, tuple_
from sqlalchemy.orm import InstrumentedAttribute, Session

from mock_api.errors import ApiError

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

LimitParam = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
CursorParam = Annotated[str | None, Query(max_length=512)]

Kind = Literal["str", "datetime"]


@dataclass(frozen=True, slots=True)
class Keyset:
    """Sort columns of a list endpoint (unique together) and their direction."""

    columns: tuple[InstrumentedAttribute[Any], ...]
    kinds: tuple[Kind, ...]
    descending: bool = False


def encode_cursor(values: Sequence[Any]) -> str:
    plain = [v.isoformat() if isinstance(v, datetime) else v for v in values]
    raw = json.dumps(plain, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, kinds: Sequence[Kind]) -> list[Any]:
    invalid = ApiError(400, "invalid_cursor", "The cursor is malformed or expired.")
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        values = json.loads(raw)
    except (binascii.Error, ValueError):
        raise invalid from None
    if not isinstance(values, list) or len(values) != len(kinds):
        raise invalid
    decoded: list[Any] = []
    for value, kind in zip(values, kinds, strict=True):
        if not isinstance(value, str):
            raise invalid
        if kind == "datetime":
            try:
                decoded.append(datetime.fromisoformat(value))
            except ValueError:
                raise invalid from None
        else:
            decoded.append(value)
    return decoded


def paginate[T](
    session: Session, stmt: Select[T], keyset: Keyset, limit: int, cursor: str | None
) -> tuple[list[T], str | None]:
    """One page of `stmt` after `cursor`, and the cursor for the next page (or None)."""
    columns = keyset.columns
    if cursor is not None:
        after = decode_cursor(cursor, keyset.kinds)
        key = tuple_(*columns)
        stmt = stmt.where(key < tuple_(*after) if keyset.descending else key > tuple_(*after))
    order = [c.desc() if keyset.descending else c.asc() for c in columns]
    rows = list(session.scalars(stmt.order_by(*order).limit(limit + 1)))
    if len(rows) <= limit:
        return rows, None
    rows = rows[:limit]
    last = rows[-1]
    return rows, encode_cursor([getattr(last, c.key) for c in columns])
