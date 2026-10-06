"""Request and response models of the order API."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mock_api.enums import ItemCondition, ReturnReason


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    data: list[T]
    next_cursor: str | None


class CustomerOut(Model):
    id: str
    name: str
    email: str
    phone: str
    address_line: str
    city: str
    postcode: str
    country: str
    created_at: datetime


class ProductOut(Model):
    sku: str
    name: str
    category: str
    product_type: str
    supplier_id: str
    list_price: Decimal
    weight_g: int | None
    length_cm: int | None
    height_cm: int | None
    width_cm: int | None
    is_hygiene: bool
    is_outlet: bool


class OrderItemOut(Model):
    id: int
    line_no: int
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    shipping_fee: Decimal


class OrderSummaryOut(Model):
    id: str
    customer_id: str
    # Stored value, as-is: orders placed before the v2 go-live use the legacy enum.
    status: str
    placed_at: datetime
    paid_at: datetime | None
    currency: str
    subtotal: Decimal
    shipping_fee: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    coupon_code: str | None
    payment_method: str


class OrderOut(OrderSummaryOut):
    items: list[OrderItemOut]


class ShipmentOut(Model):
    id: str
    order_id: str
    carrier: str
    tracking_number: str
    status: str
    shipped_at: datetime | None
    estimated_delivery_at: datetime | None
    delivered_at: datetime | None


class ReturnItemOut(Model):
    order_item_id: int
    quantity: int
    condition: str


class ReturnOut(Model):
    id: str
    order_id: str
    status: str
    reason: str
    resolution: str | None
    requested_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    refund_amount: Decimal | None
    customer_comment: str | None
    agent_note: str | None
    source: str
    items: list[ReturnItemOut]


class ReturnItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_item_id: int
    quantity: int = Field(ge=1)
    condition: ItemCondition


class ReturnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=1, max_length=16)
    reason: ReturnReason
    items: list[ReturnItemIn] = Field(min_length=1, max_length=50)
    customer_comment: str | None = Field(default=None, max_length=500)

    @field_validator("items")
    @classmethod
    def _distinct_items(cls, items: list[ReturnItemIn]) -> list[ReturnItemIn]:
        ids = [i.order_item_id for i in items]
        if len(set(ids)) != len(ids):
            raise ValueError("each order_item_id may appear only once")
        return items
