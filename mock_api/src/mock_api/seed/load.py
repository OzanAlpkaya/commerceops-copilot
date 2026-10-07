"""Writing a SeedDataset into lumora_commerce, replacing whatever was there."""

from collections.abc import Iterable, Sequence
from dataclasses import asdict
from typing import Any

from sqlalchemy import Connection, Engine, insert, text

from mock_api.models import Base
from mock_api.seed.dataset import SeedDataset

# Insert order (foreign keys first). idempotency_keys is recreated empty.
SEEDED_TABLES = (
    "suppliers",
    "products",
    "customers",
    "orders",
    "order_items",
    "shipments",
    "returns",
    "return_items",
)
FIRST_RETURN_NUMBER = 100001
BATCH = 5000


def _rows(ds: SeedDataset) -> dict[str, Sequence[Any]]:
    return {
        "suppliers": ds.suppliers,
        "products": ds.products,
        "customers": ds.customers,
        "orders": [o.order for o in ds.orders],
        "order_items": [i for o in ds.orders for i in o.items],
        "shipments": [o.shipment for o in ds.orders if o.shipment is not None],
        "returns": ds.returns.returns,
        "return_items": ds.returns.items,
    }


def _batches(rows: Sequence[Any]) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), BATCH):
        yield [asdict(row) for row in rows[start : start + BATCH]]


def load_dataset(engine: Engine, ds: SeedDataset) -> None:
    """Drop and recreate every table, then insert the dataset, in one transaction.

    Running it twice leaves identical tables. Returns created through the API and stored
    idempotency keys are wiped too: the database goes back to the seed state.
    """
    rows = _rows(ds)
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
        for name in SEEDED_TABLES:
            for batch in _batches(rows[name]):
                conn.execute(insert(Base.metadata.tables[name]), batch)
        # The next API-created return continues the RMA- numbering.
        seeded = len(ds.returns.returns)
        conn.execute(
            text("SELECT setval('return_number_seq', :value, :called)"),
            {"value": FIRST_RETURN_NUMBER + max(seeded - 1, 0), "called": seeded > 0},
        )


def table_checksums(conn: Connection) -> dict[str, str]:
    """md5 over every row of every seeded table, in a stable order."""
    return {
        name: conn.execute(
            text(
                f"SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM {name} t"
            )
        ).scalar_one()
        for name in SEEDED_TABLES
    }
