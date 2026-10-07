"""A small synthetic Olist dataset, written as CSVs with Olist's real headers.

Olist is not in the repo or in CI, so tests (the seed's and the corpus generators') run on
this instead. It is generated deterministically and sized so that every undecided-rule
quota can be met with the small quotas in `fixture_config`.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from mock_api.seed.config import SeedConfig
from mock_api.seed.olist import (
    CUSTOMERS_CSV,
    ITEMS_CSV,
    ORDERS_CSV,
    PAYMENTS_CSV,
    PRODUCTS_CSV,
    REVIEWS_CSV,
)

N_ORDERS = 600
N_CUSTOMERS = 390
PRODUCT_MIX = (
    ("cama_mesa_banho", 50, (100, 6000)),
    ("moveis_decoracao", 25, (100, 30000)),
    ("utilidades_domesticas", 20, (100, 8000)),
    ("moveis_escritorio", 10, (500, 30000)),
    ("moveis_colchao_e_estofado", 5, (2000, 40000)),
    ("beleza_saude", 10, (50, 1000)),  # not a home category
)
START = datetime(2017, 1, 2)
END = datetime(2018, 8, 31)
TS = "%Y-%m-%d %H:%M:%S"


def _hex(r: random.Random) -> str:
    return f"{r.getrandbits(128):032x}"


def _write(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def write_olist_fixture(directory: Path) -> None:
    r = random.Random(7)
    products: list[tuple[str, str]] = []
    product_rows: list[list[object]] = []
    for category, count, (lo, hi) in PRODUCT_MIX:
        for _ in range(count):
            pid = _hex(r)
            products.append((pid, category))
            product_rows.append(
                [
                    pid,
                    category,
                    40,
                    300,
                    1,
                    r.randint(lo, hi),
                    r.randint(10, 100),
                    r.randint(5, 80),
                    r.randint(10, 60),
                ]
            )
    home = [p for p in products if p[1] != "beleza_saude"]
    other = [p for p in products if p[1] == "beleza_saude"]
    sellers = [_hex(r) for _ in range(15)]
    uniques = [_hex(r) for _ in range(N_CUSTOMERS)]

    orders, items, payments, customers, reviews = [], [], [], [], []
    span = (END - START).total_seconds()
    for n in range(N_ORDERS):
        oid, cid = _hex(r), _hex(r)
        customers.append([cid, uniques[n % N_CUSTOMERS], "01001", "sao paulo", "SP"])
        # A third of the orders fall in the last two months, so recent (open) returns
        # have enough candidates; a few land in the last week with quick delivery, so
        # recent delivered orders exist for the in-transit step.
        bucket = r.random()
        if bucket < 0.06:
            purchased = END - timedelta(days=r.random() * 7)
        elif bucket < 0.35:
            purchased = END - timedelta(days=r.random() * 60)
        else:
            purchased = START + timedelta(seconds=r.random() * span)
        status = r.choices(
            ["delivered", "shipped", "canceled", "processing", "invoiced"],
            weights=[94, 2, 1, 2, 1],
        )[0]
        approved = purchased + timedelta(hours=r.uniform(0.2, 30))
        carrier = approved + timedelta(days=r.uniform(0.5, 3))
        # Half the deliveries are quick, so recent delivered orders exist too.
        quick = bucket < 0.06 or r.random() < 0.5
        delivered = carrier + timedelta(
            days=r.uniform(0.5, 3 if bucket < 0.06 else 6 if quick else 40)
        )
        estimated = purchased + timedelta(days=20)
        orders.append(
            [
                oid,
                cid,
                status,
                purchased.strftime(TS),
                approved.strftime(TS),
                carrier.strftime(TS) if status in ("delivered", "shipped") else "",
                delivered.strftime(TS) if status == "delivered" else "",
                estimated.strftime("%Y-%m-%d 00:00:00"),
            ]
        )
        chosen = [r.choice(home) for _ in range(r.choice([1, 1, 1, 2, 3]))]
        if r.random() < 0.05:
            chosen.append(r.choice(other))
        total = 0.0
        for item_no, (pid, _) in enumerate(chosen, start=1):
            price, freight = round(r.uniform(10, 400), 2), round(r.uniform(5, 40), 2)
            total += price + freight
            items.append(
                [oid, item_no, pid, r.choice(sellers), purchased.strftime(TS), price, freight]
            )
        if r.random() < 0.2:
            payments.append([oid, 1, "voucher", 1, round(total * 0.2, 2)])
            payments.append([oid, 2, "credit_card", 3, round(total * 0.8, 2)])
        else:
            payments.append([oid, 1, r.choice(["credit_card", "boleto"]), 1, round(total, 2)])
        reviews.append(
            [_hex(r), oid, r.randint(1, 5), "", "", purchased.strftime(TS), purchased.strftime(TS)]
        )
    # An order without items, as in the real data.
    orders.append(
        [
            _hex(r),
            customers[0][0],
            "unavailable",
            START.strftime(TS),
            "",
            "",
            "",
            START.strftime(TS),
        ]
    )

    _write(
        directory / PRODUCTS_CSV,
        [
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ],
        product_rows,
    )
    _write(
        directory / ORDERS_CSV,
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        orders,
    )
    _write(
        directory / ITEMS_CSV,
        [
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ],
        items,
    )
    _write(
        directory / PAYMENTS_CSV,
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
        payments,
    )
    _write(
        directory / CUSTOMERS_CSV,
        [
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ],
        customers,
    )
    _write(
        directory / REVIEWS_CSV,
        [
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ],
        reviews,
    )


def fixture_config(olist_dir: Path) -> SeedConfig:
    """Seed knobs scaled down to the fixture."""
    return SeedConfig(
        _env_file=None,  # type: ignore[call-arg]
        source_dir=olist_dir,
        target_orders=450,
        supplier_count=8,
        outlet_share=0.2,
        return_rate=0.12,
        quota_window=6,
        quota_outlet=3,
        quota_coupon=3,
        quota_hygiene=4,
        open_per_rule=2,
        open_eligible=2,
        open_ineligible=2,
        open_in_progress=2,
        lost_parcels=2,
        recent_transit=20,  # more than the fixture has in transit, so delivered orders top up
    )
