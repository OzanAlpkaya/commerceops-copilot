"""Rows the seed inserts. Field names match the columns in mock_api.models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SupplierRow:
    id: str
    name: str
    country: str
    contact_email: str


@dataclass(frozen=True, slots=True)
class ProductRow:
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


@dataclass(frozen=True, slots=True)
class CustomerRow:
    id: str
    name: str
    email: str
    phone: str
    address_line: str
    city: str
    postcode: str
    country: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OrderRow:
    id: str
    customer_id: str
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


@dataclass(frozen=True, slots=True)
class OrderItemRow:
    id: int
    order_id: str
    line_no: int
    sku: str
    quantity: int
    unit_price: Decimal
    shipping_fee: Decimal


@dataclass(frozen=True, slots=True)
class ShipmentRow:
    id: str
    order_id: str
    carrier: str
    tracking_number: str
    status: str
    shipped_at: datetime | None
    estimated_delivery_at: datetime | None
    delivered_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReturnRow:
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
    api_client: str | None


@dataclass(frozen=True, slots=True)
class ReturnItemRow:
    return_id: str
    order_item_id: int
    quantity: int
    condition: str
