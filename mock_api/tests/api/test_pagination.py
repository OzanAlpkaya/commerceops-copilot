import base64
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from mock_api.models import Order

Headers = Callable[..., dict[str, str]]
BASE = datetime(2026, 5, 1, tzinfo=UTC)


def add_orders(
    engine: Engine, ids_and_days: list[tuple[str, int]], status: str = "delivered"
) -> None:
    with Session(engine) as session:
        session.add_all(
            Order(
                id=order_id,
                customer_id="CUS-000002",
                status=status,
                placed_at=BASE + timedelta(days=day),
                paid_at=None,
                currency="EUR",
                subtotal=Decimal(10),
                shipping_fee=Decimal(0),
                discount_amount=Decimal(0),
                total_amount=Decimal(10),
                payment_method="card",
            )
            for order_id, day in ids_and_days
        )
        session.commit()


def walk(client: TestClient, headers: Headers, path: str, **params: object) -> list[list[str]]:
    pages: list[list[str]] = []
    cursor = None
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        body = client.get(path, params=query, headers=headers()).json()
        key = "sku" if path == "/products" else "id"
        pages.append([row[key] for row in body["data"]])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages


def test_walk_returns_every_row_once_newest_first(client, headers, engine) -> None:
    add_orders(engine, [(f"LH-20000{i:02d}", i) for i in range(7)])

    pages = walk(client, headers, "/orders", customer_id="CUS-000002", limit=3)

    ids = [i for page in pages for i in page]
    assert [len(p) for p in pages] == [3, 3, 2]  # LH-1000003 (October) + 7 May orders
    assert len(ids) == len(set(ids)) == 8
    assert ids == ["LH-1000003", *[f"LH-20000{i:02d}" for i in reversed(range(7))]]


def test_filters_hold_across_pages(client, headers, engine) -> None:
    add_orders(engine, [(f"LH-30000{i:02d}", i) for i in range(5)], status="canceled")
    add_orders(engine, [(f"LH-40000{i:02d}", i) for i in range(5)], status="delivered")

    ids = [i for p in walk(client, headers, "/orders", status="canceled", limit=2) for i in p]

    assert sorted(ids) == [f"LH-30000{i:02d}" for i in range(5)]


def test_same_timestamp_is_broken_by_id(client, headers, engine) -> None:
    add_orders(engine, [(f"LH-50000{i:02d}", 0) for i in range(5)])

    ids = [
        i for p in walk(client, headers, "/orders", customer_id="CUS-000002", limit=2) for i in p
    ]

    assert len(ids) == len(set(ids)) == 6


def test_rows_inserted_mid_walk_cause_no_duplicates(client, headers, engine) -> None:
    add_orders(engine, [(f"LH-60000{i:02d}", i) for i in range(6)])
    first = client.get(
        "/orders", params={"customer_id": "CUS-000002", "limit": 3}, headers=headers()
    )
    seen = [o["id"] for o in first.json()["data"]]

    add_orders(engine, [("LH-6000099", 99), ("LH-6000098", -99)])  # one newer, one older
    rest = walk(
        client,
        headers,
        "/orders",
        customer_id="CUS-000002",
        limit=3,
        cursor=first.json()["next_cursor"],
    )

    later = [i for p in rest for i in p]
    assert not set(seen) & set(later)
    assert "LH-6000098" in later and "LH-6000099" not in later


def test_products_and_customers_paginate_by_key(client, headers) -> None:
    assert walk(client, headers, "/products", limit=2) == [
        ["LUM-BED-10001", "LUM-DEC-10002"],
        ["LUM-HSW-10003"],
    ]
    assert walk(client, headers, "/customers", limit=1) == [["CUS-000001"], ["CUS-000002"]]


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_limit_bounds(client: TestClient, headers: Headers, limit: int) -> None:
    response = client.get("/orders", params={"limit": limit}, headers=headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "cursor",
    [
        "not-base64!!",
        base64.urlsafe_b64encode(b'{"a": 1}').decode(),  # not a list
        base64.urlsafe_b64encode(b'["2026-01-01T00:00:00+00:00"]').decode(),  # wrong length
        base64.urlsafe_b64encode(b'["yesterday", "LH-1"]').decode(),  # not a timestamp
    ],
)
def test_tampered_cursor_is_400(client: TestClient, headers: Headers, cursor: str) -> None:
    response = client.get("/orders", params={"cursor": cursor}, headers=headers())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_list_envelope(client: TestClient, headers: Headers) -> None:
    body = client.get("/returns", params={"order_id": "LH-1000002"}, headers=headers()).json()
    assert body["next_cursor"] is None
    assert [r["id"] for r in body["data"]] == ["RMA-100001"]
    assert body["data"][0]["items"] == [
        {"order_item_id": 3, "quantity": 1, "condition": "unopened"}
    ]
