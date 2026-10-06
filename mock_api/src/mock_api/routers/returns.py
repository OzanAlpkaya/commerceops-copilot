from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mock_api.config import ApiClient
from mock_api.db import SessionDep
from mock_api.enums import LegacyOrderStatus, OrderStatus, ReturnSource, ReturnStatus
from mock_api.errors import ApiError, not_found
from mock_api.idempotency import replay, request_hash, require_key
from mock_api.models import IdempotencyKey, Order, OrderItem, Return, ReturnItem
from mock_api.pagination import DEFAULT_LIMIT, CursorParam, Keyset, LimitParam, paginate
from mock_api.schemas import Page, ReturnCreate, ReturnItemOut, ReturnOut
from mock_api.security import rate_limited_client, require_scope

router = APIRouter(prefix="/returns", tags=["returns"], dependencies=[Depends(rate_limited_client)])

KEYSET = Keyset((Return.requested_at, Return.id), ("datetime", "str"), descending=True)
DELIVERED = {OrderStatus.DELIVERED.value, LegacyOrderStatus.COMPLETED.value}


def _with_items(session: Session, returns: Sequence[Return]) -> list[ReturnOut]:
    items: defaultdict[str, list[ReturnItemOut]] = defaultdict(list)
    if returns:
        rows = session.scalars(
            select(ReturnItem)
            .where(ReturnItem.return_id.in_([r.id for r in returns]))
            .order_by(ReturnItem.return_id, ReturnItem.order_item_id)
        )
        for row in rows:
            items[row.return_id].append(ReturnItemOut.model_validate(row))
    return [ReturnOut.model_validate({**_columns(r), "items": items[r.id]}) for r in returns]


def _columns(r: Return) -> dict[str, object]:
    return {c.key: getattr(r, c.key) for c in Return.__table__.columns}


@router.get("/{return_id}")
def get_return(return_id: str, session: SessionDep) -> ReturnOut:
    ret = session.get(Return, return_id)
    if ret is None:
        raise not_found("return", return_id)
    return _with_items(session, [ret])[0]


@router.get("")
def list_returns(
    session: SessionDep,
    order_id: Annotated[str | None, Query(max_length=16)] = None,
    limit: LimitParam = DEFAULT_LIMIT,
    cursor: CursorParam = None,
) -> Page[ReturnOut]:
    stmt = select(Return)
    if order_id is not None:
        stmt = stmt.where(Return.order_id == order_id)
    rows, next_cursor = paginate(session, stmt, KEYSET, limit, cursor)
    return Page(data=_with_items(session, rows), next_cursor=next_cursor)


def _check_returnable(session: Session, body: ReturnCreate) -> None:
    """Structural checks only. Like the real order system, no policy window is enforced."""
    order = session.get(Order, body.order_id)
    if order is None:
        raise not_found("order", body.order_id)
    if order.status not in DELIVERED:
        raise ApiError(
            422, "order_not_delivered", f"Order {order.id} is {order.status!r}, not delivered."
        )
    ordered = {
        i.id: i.quantity
        for i in session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
    }
    # A comprehension, not dict(): Result has .keys() and would be read as a mapping.
    already = {
        item_id: total
        for item_id, total in session.execute(
            select(ReturnItem.order_item_id, func.sum(ReturnItem.quantity))
            .join(Return, Return.id == ReturnItem.return_id)
            .where(
                ReturnItem.order_item_id.in_(list(ordered)),
                Return.status != ReturnStatus.REJECTED,
            )
            .group_by(ReturnItem.order_item_id)
        )
    }
    for item in body.items:
        if item.order_item_id not in ordered:
            raise ApiError(
                422,
                "item_not_in_order",
                f"Order item {item.order_item_id} does not belong to order {order.id}.",
            )
        returnable = ordered[item.order_item_id] - int(already.get(item.order_item_id, 0))
        if item.quantity > returnable:
            raise ApiError(
                422,
                "quantity_exceeds_returnable",
                f"Order item {item.order_item_id}: {returnable} left to return, "
                f"{item.quantity} requested.",
            )


@router.post("", status_code=201, responses={201: {"model": ReturnOut}})
def create_return(
    body: ReturnCreate,
    session: SessionDep,
    client: Annotated[ApiClient, Depends(require_scope("write"))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    key = require_key(idempotency_key)
    body_hash = request_hash(body)
    if (previous := replay(session, client.name, key, body_hash)) is not None:
        return previous

    _check_returnable(session, body)
    now = datetime.now(UTC).replace(microsecond=0)
    ret = Return(
        order_id=body.order_id,
        status=ReturnStatus.REQUESTED.value,
        reason=body.reason.value,
        requested_at=now,
        updated_at=now,
        customer_comment=body.customer_comment,
        source=ReturnSource.API.value,
        api_client=client.name,
    )
    session.add(ret)
    session.flush()  # assigns the RMA- id from the sequence
    session.add_all(
        ReturnItem(
            return_id=ret.id,
            order_item_id=item.order_item_id,
            quantity=item.quantity,
            condition=item.condition.value,
        )
        for item in body.items
    )
    session.flush()
    content = _with_items(session, [ret])[0].model_dump(mode="json")
    session.add(
        IdempotencyKey(
            api_client=client.name,
            key=key,
            request_hash=body_hash,
            response_status=201,
            response_body=content,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        # A concurrent request with the same key won the race: answer as it did.
        session.rollback()
        previous = replay(session, client.name, key, body_hash)
        if previous is None:
            raise
        return previous
    return JSONResponse(content, status_code=201, headers={"Location": f"/returns/{ret.id}"})
