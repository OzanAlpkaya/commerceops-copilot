"""Tables of the lumora_commerce database."""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Sequence,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from mock_api.enums import (
    ItemCondition,
    LegacyOrderStatus,
    OrderStatus,
    PaymentMethod,
    ReturnReason,
    ReturnResolution,
    ReturnSource,
    ReturnStatus,
    ShipmentStatus,
)

Money = Numeric(10, 2)
Timestamp = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


return_number_seq = Sequence("return_number_seq", start=100001, metadata=Base.metadata)


def _one_of(column: str, values: Iterable[StrEnum]) -> str:
    quoted = ", ".join(f"'{v.value}'" for v in values)
    return f"{column} IN ({quoted})"


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(64))
    contact_email: Mapped[str] = mapped_column(String(254))


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_supplier_sku", "supplier_id", "sku"),)

    sku: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    product_type: Mapped[str] = mapped_column(String(64))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    list_price: Mapped[Decimal] = mapped_column(Money)
    weight_g: Mapped[int | None] = mapped_column(Integer)
    length_cm: Mapped[int | None] = mapped_column(Integer)
    height_cm: Mapped[int | None] = mapped_column(Integer)
    width_cm: Mapped[int | None] = mapped_column(Integer)
    is_hygiene: Mapped[bool]
    is_outlet: Mapped[bool]


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_email_lower", func.lower(text("email")), unique=True),)

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(32))
    address_line: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(80))
    postcode: Mapped[str] = mapped_column(String(16))
    country: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(Timestamp)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            _one_of("status", [*OrderStatus, *LegacyOrderStatus]), name="ck_orders_status"
        ),
        CheckConstraint(_one_of("payment_method", PaymentMethod), name="ck_orders_payment"),
        Index("ix_orders_customer_placed", "customer_id", "placed_at", "id"),
        Index("ix_orders_placed", "placed_at", "id"),
        Index("ix_orders_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[str] = mapped_column(String(16))
    placed_at: Mapped[datetime] = mapped_column(Timestamp)
    paid_at: Mapped[datetime | None] = mapped_column(Timestamp)
    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[Decimal] = mapped_column(Money)
    shipping_fee: Mapped[Decimal] = mapped_column(Money)
    discount_amount: Mapped[Decimal] = mapped_column(Money)
    total_amount: Mapped[Decimal] = mapped_column(Money)
    coupon_code: Mapped[str | None] = mapped_column(String(32))
    payment_method: Mapped[str] = mapped_column(String(16))


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "line_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    line_no: Mapped[int]
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Money)
    shipping_fee: Mapped[Decimal] = mapped_column(Money)


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = (
        CheckConstraint(_one_of("status", ShipmentStatus), name="ck_shipments_status"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    carrier: Mapped[str] = mapped_column(String(40))
    tracking_number: Mapped[str] = mapped_column(String(40), unique=True)
    status: Mapped[str] = mapped_column(String(16))
    shipped_at: Mapped[datetime | None] = mapped_column(Timestamp)
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(Timestamp)
    delivered_at: Mapped[datetime | None] = mapped_column(Timestamp)


class Return(Base):
    __tablename__ = "returns"
    __table_args__ = (
        CheckConstraint(_one_of("status", ReturnStatus), name="ck_returns_status"),
        CheckConstraint(_one_of("reason", ReturnReason), name="ck_returns_reason"),
        CheckConstraint(_one_of("resolution", ReturnResolution), name="ck_returns_resolution"),
        CheckConstraint(_one_of("source", ReturnSource), name="ck_returns_source"),
        Index("ix_returns_order", "order_id"),
        Index("ix_returns_requested", "requested_at", "id"),
    )

    id: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
        server_default=text("'RMA-' || nextval('return_number_seq')"),
    )
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(24))
    resolution: Mapped[str | None] = mapped_column(String(16))
    requested_at: Mapped[datetime] = mapped_column(Timestamp)
    updated_at: Mapped[datetime] = mapped_column(Timestamp)
    closed_at: Mapped[datetime | None] = mapped_column(Timestamp)
    refund_amount: Mapped[Decimal | None] = mapped_column(Money)
    customer_comment: Mapped[str | None] = mapped_column(String(500))
    agent_note: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(16))
    api_client: Mapped[str | None] = mapped_column(String(64))


class ReturnItem(Base):
    __tablename__ = "return_items"
    __table_args__ = (
        CheckConstraint(_one_of("condition", ItemCondition), name="ck_return_items_condition"),
    )

    return_id: Mapped[str] = mapped_column(ForeignKey("returns.id"), primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), primary_key=True)
    quantity: Mapped[int]
    condition: Mapped[str] = mapped_column(String(16))


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    api_client: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int]
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=func.now())
