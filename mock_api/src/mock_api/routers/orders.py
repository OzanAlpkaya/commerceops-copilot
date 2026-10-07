from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from mock_api.db import SessionDep
from mock_api.errors import not_found
from mock_api.models import Order, OrderItem, Product, Shipment
from mock_api.pagination import DEFAULT_LIMIT, CursorParam, Keyset, LimitParam, paginate
from mock_api.schemas import OrderItemOut, OrderOut, OrderSummaryOut, Page, ShipmentOut
from mock_api.security import rate_limited_client

router = APIRouter(prefix="/orders", tags=["orders"], dependencies=[Depends(rate_limited_client)])

KEYSET = Keyset((Order.placed_at, Order.id), ("datetime", "str"), descending=True)

# Either enum is accepted, and the filter matches the stored value literally:
# status=delivered does not return legacy COMPLETED orders.
StatusFilter = Literal[
    "pending",
    "processing",
    "shipped",
    "delivered",
    "canceled",
    "NEW",
    "PAID",
    "INVOICED",
    "PICKING",
    "DISPATCHED",
    "COMPLETED",
    "CANCELLED",
]


@router.get("/{order_id}")
def get_order(order_id: str, session: SessionDep) -> OrderOut:
    order = session.get(Order, order_id)
    if order is None:
        raise not_found("order", order_id)
    lines = session.execute(
        select(OrderItem, Product.name)
        .join(Product, Product.sku == OrderItem.sku)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.line_no)
    ).all()
    items = [
        OrderItemOut(
            id=item.id,
            line_no=item.line_no,
            sku=item.sku,
            product_name=name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            shipping_fee=item.shipping_fee,
        )
        for item, name in lines
    ]
    summary = OrderSummaryOut.model_validate(order)
    return OrderOut(**summary.model_dump(), items=items)


@router.get("/{order_id}/shipment")
def get_order_shipment(order_id: str, session: SessionDep) -> ShipmentOut:
    if session.get(Order, order_id) is None:
        raise not_found("order", order_id)
    shipment = session.scalar(select(Shipment).where(Shipment.order_id == order_id))
    if shipment is None:
        raise not_found("shipment", order_id)
    return ShipmentOut.model_validate(shipment)


@router.get("")
def list_orders(
    session: SessionDep,
    customer_id: Annotated[str | None, Query(max_length=16)] = None,
    status: StatusFilter | None = None,
    limit: LimitParam = DEFAULT_LIMIT,
    cursor: CursorParam = None,
) -> Page[OrderSummaryOut]:
    stmt = select(Order)
    if customer_id is not None:
        stmt = stmt.where(Order.customer_id == customer_id)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    rows, next_cursor = paginate(session, stmt, KEYSET, limit, cursor)
    return Page(data=[OrderSummaryOut.model_validate(o) for o in rows], next_cursor=next_cursor)
