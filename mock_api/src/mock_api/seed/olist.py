"""Typed readers for the Olist CSV files the seed needs."""

import csv
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from mock_api.seed.errors import SeedError

ORDERS_CSV = "olist_orders_dataset.csv"
ITEMS_CSV = "olist_order_items_dataset.csv"
PRODUCTS_CSV = "olist_products_dataset.csv"
PAYMENTS_CSV = "olist_order_payments_dataset.csv"
CUSTOMERS_CSV = "olist_customers_dataset.csv"
REVIEWS_CSV = "olist_order_reviews_dataset.csv"

REQUIRED_FILES = (ORDERS_CSV, ITEMS_CSV, PRODUCTS_CSV, PAYMENTS_CSV, CUSTOMERS_CSV, REVIEWS_CSV)


@dataclass(frozen=True, slots=True)
class OlistOrder:
    order_id: str
    customer_id: str
    status: str
    purchased_at: datetime
    approved_at: datetime | None
    carrier_at: datetime | None
    delivered_at: datetime | None
    estimated_at: datetime | None


@dataclass(frozen=True, slots=True)
class OlistItem:
    order_id: str
    item_no: int
    product_id: str
    seller_id: str
    price: Decimal
    freight: Decimal


@dataclass(frozen=True, slots=True)
class OlistProduct:
    product_id: str
    category: str
    weight_g: int | None
    length_cm: int | None
    height_cm: int | None
    width_cm: int | None


@dataclass(frozen=True, slots=True)
class OlistPayment:
    order_id: str
    sequential: int
    payment_type: str
    value: Decimal


@dataclass(frozen=True, slots=True)
class OlistData:
    orders: dict[str, OlistOrder]
    items: dict[str, list[OlistItem]]  # by order_id, sorted by item_no
    products: dict[str, OlistProduct]
    payments: dict[str, list[OlistPayment]]  # by order_id
    customer_unique_ids: dict[str, str]  # customer_id -> customer_unique_id
    review_scores: dict[str, int]  # order_id -> lowest review score


def _rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def _ts(value: str) -> datetime | None:
    return datetime.fromisoformat(value).replace(tzinfo=UTC) if value else None


def _int(value: str) -> int | None:
    return int(float(value)) if value else None


def load_olist(source_dir: Path) -> OlistData:
    missing = [name for name in REQUIRED_FILES if not (source_dir / name).is_file()]
    if missing:
        raise SeedError(
            f"Olist CSVs missing in {source_dir}: {', '.join(missing)}. "
            "Download the Brazilian E-Commerce Public Dataset by Olist and unpack it there."
        )

    orders: dict[str, OlistOrder] = {}
    for r in _rows(source_dir / ORDERS_CSV):
        purchased_at = _ts(r["order_purchase_timestamp"])
        if purchased_at is None:
            continue
        orders[r["order_id"]] = OlistOrder(
            order_id=r["order_id"],
            customer_id=r["customer_id"],
            status=r["order_status"],
            purchased_at=purchased_at,
            approved_at=_ts(r["order_approved_at"]),
            carrier_at=_ts(r["order_delivered_carrier_date"]),
            delivered_at=_ts(r["order_delivered_customer_date"]),
            estimated_at=_ts(r["order_estimated_delivery_date"]),
        )

    items: defaultdict[str, list[OlistItem]] = defaultdict(list)
    for r in _rows(source_dir / ITEMS_CSV):
        items[r["order_id"]].append(
            OlistItem(
                order_id=r["order_id"],
                item_no=int(r["order_item_id"]),
                product_id=r["product_id"],
                seller_id=r["seller_id"],
                price=Decimal(r["price"]),
                freight=Decimal(r["freight_value"]),
            )
        )
    for order_items in items.values():
        order_items.sort(key=lambda i: i.item_no)

    products = {
        r["product_id"]: OlistProduct(
            product_id=r["product_id"],
            category=r["product_category_name"],
            weight_g=_int(r["product_weight_g"]),
            length_cm=_int(r["product_length_cm"]),
            height_cm=_int(r["product_height_cm"]),
            width_cm=_int(r["product_width_cm"]),
        )
        for r in _rows(source_dir / PRODUCTS_CSV)
    }

    payments: defaultdict[str, list[OlistPayment]] = defaultdict(list)
    for r in _rows(source_dir / PAYMENTS_CSV):
        payments[r["order_id"]].append(
            OlistPayment(
                order_id=r["order_id"],
                sequential=int(r["payment_sequential"]),
                payment_type=r["payment_type"],
                value=Decimal(r["payment_value"]),
            )
        )

    customer_unique_ids = {
        r["customer_id"]: r["customer_unique_id"] for r in _rows(source_dir / CUSTOMERS_CSV)
    }

    review_scores: dict[str, int] = {}
    for r in _rows(source_dir / REVIEWS_CSV):
        score = int(r["review_score"])
        previous = review_scores.get(r["order_id"])
        review_scores[r["order_id"]] = score if previous is None else min(previous, score)

    return OlistData(
        orders=orders,
        items=dict(items),
        products=products,
        payments=dict(payments),
        customer_unique_ids=customer_unique_ids,
        review_scores=review_scores,
    )
