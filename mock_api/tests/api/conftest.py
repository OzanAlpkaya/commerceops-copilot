"""API test fixtures: a small fixed dataset in lumora_commerce_test and a TestClient."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from mock_api.config import Settings
from mock_api.main import create_app
from mock_api.models import (
    Base,
    Customer,
    Order,
    OrderItem,
    Product,
    Return,
    ReturnItem,
    Shipment,
    Supplier,
)

READ_KEY = "test-read-key"
WRITE_KEY = "test-write-key"
OPS_KEY = "test-ops-key"
KEYS = f"copilot:{READ_KEY}:read,admin:{WRITE_KEY}:read+write,ops:{OPS_KEY}:read+write"


KEY_BY_CLIENT = {"copilot": READ_KEY, "admin": WRITE_KEY, "ops": OPS_KEY}

Headers = Callable[..., dict[str, str]]


@pytest.fixture
def headers() -> Headers:
    """headers("admin", **{"Idempotency-Key": "k"}) -> request headers for that client."""

    def make(client: str = "copilot", **extra: str) -> dict[str, str]:
        return {"X-API-Key": KEY_BY_CLIENT.get(client, client), **extra}

    return make


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def ts(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=UTC)


def _order(order_id: str, customer: str, status: str, placed: str, **extra: object) -> Order:
    return Order(
        id=order_id,
        customer_id=customer,
        status=status,
        placed_at=ts(placed),
        paid_at=ts(placed),
        currency="EUR",
        subtotal=Decimal("100.00"),
        shipping_fee=Decimal("10.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("110.00"),
        payment_method="card",
        **extra,
    )


def _product(sku: str, name: str, **flags: bool) -> Product:
    return Product(
        sku=sku,
        name=name,
        category="bedding_bath",
        product_type="Pillow",
        supplier_id="SUP-001",
        list_price=Decimal("29.90"),
        weight_g=800,
        length_cm=50,
        height_cm=10,
        width_cm=40,
        is_hygiene=flags.get("hygiene", False),
        is_outlet=flags.get("outlet", False),
    )


def load_fixture_rows(session: Session) -> None:
    session.add(
        Supplier(
            id="SUP-001",
            name="Cedarstead Textiles",
            country="Portugal",
            contact_email="orders@cedarstead.example",
        )
    )
    session.flush()
    session.add_all(
        [
            _product("LUM-BED-10001", "Aster Microfibre Pillow – King", hygiene=True),
            _product("LUM-DEC-10002", "Fern Ceramic Vase – Sage", outlet=True),
            _product("LUM-HSW-10003", "Oslo Glass Storage Jar Set – Set of 3, White"),
        ]
    )
    session.add_all(
        [
            Customer(
                id="CUS-000001",
                name="Aoife Murphy",
                email="aoife.murphy@example.com",
                phone="+353 85 111 2222",
                address_line="1 Main Street",
                city="Cork",
                postcode="T12 AB12",
                country="IE",
                created_at=ts("2025-06-01"),
            ),
            Customer(
                id="CUS-000002",
                name="Cian Walsh",
                email="cian.walsh@example.net",
                phone="+353 86 333 4444",
                address_line="2 Quay Street",
                city="Galway",
                postcode="H91 CD34",
                country="IE",
                created_at=ts("2026-04-01"),
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            _order("LH-1000001", "CUS-000001", "COMPLETED", "2025-06-01"),  # legacy enum
            _order("LH-1000002", "CUS-000001", "delivered", "2026-04-01", coupon_code="SPRING15"),
            _order("LH-1000003", "CUS-000002", "shipped", "2026-10-01"),
        ]
    )
    session.flush()
    session.add_all(
        [
            OrderItem(
                id=1,
                order_id="LH-1000001",
                line_no=1,
                sku="LUM-HSW-10003",
                quantity=2,
                unit_price=Decimal("45.00"),
                shipping_fee=Decimal("10.00"),
            ),
            OrderItem(
                id=2,
                order_id="LH-1000002",
                line_no=1,
                sku="LUM-BED-10001",
                quantity=1,
                unit_price=Decimal("29.90"),
                shipping_fee=Decimal("5.00"),
            ),
            OrderItem(
                id=3,
                order_id="LH-1000002",
                line_no=2,
                sku="LUM-DEC-10002",
                quantity=3,
                unit_price=Decimal("23.00"),
                shipping_fee=Decimal("5.00"),
            ),
            OrderItem(
                id=4,
                order_id="LH-1000003",
                line_no=1,
                sku="LUM-HSW-10003",
                quantity=1,
                unit_price=Decimal("45.00"),
                shipping_fee=Decimal("10.00"),
            ),
        ]
    )
    session.add_all(
        [
            Shipment(
                id="SHP-0000001",
                order_id="LH-1000001",
                carrier="Parcelo",
                tracking_number="PCL000000000001",
                status="delivered",
                shipped_at=ts("2025-06-02"),
                estimated_delivery_at=ts("2025-06-10"),
                delivered_at=ts("2025-06-08"),
            ),
            Shipment(
                id="SHP-0000002",
                order_id="LH-1000002",
                carrier="NordPost",
                tracking_number="NP000000002IE",
                status="delivered",
                shipped_at=ts("2026-04-02"),
                estimated_delivery_at=ts("2026-04-12"),
                delivered_at=ts("2026-04-09"),
            ),
            Shipment(
                id="SHP-0000003",
                order_id="LH-1000003",
                carrier="SwiftLane Express",
                tracking_number="SLX-ABCD-000003",
                status="in_transit",
                shipped_at=ts("2026-10-02"),
                estimated_delivery_at=ts("2026-10-08"),
                delivered_at=None,
            ),
        ]
    )
    session.flush()
    session.add(
        Return(
            id="RMA-100001",
            order_id="LH-1000002",
            status="refunded",
            reason="changed_mind",
            resolution="refund",
            requested_at=ts("2026-04-12"),
            updated_at=ts("2026-04-25"),
            closed_at=ts("2026-04-25"),
            refund_amount=Decimal("23.00"),
            source="admin_panel",
        )
    )
    session.flush()
    session.add(
        ReturnItem(return_id="RMA-100001", order_item_id=3, quantity=1, condition="unopened")
    )
    session.commit()


@pytest.fixture
def engine(db_engine: Engine) -> Iterator[Engine]:
    """Fresh tables with the fixed rows, for every test."""
    Base.metadata.create_all(db_engine)
    with db_engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))
        conn.execute(text("ALTER SEQUENCE return_number_seq RESTART WITH 100002"))
    with Session(db_engine) as session:
        load_fixture_rows(session)
    yield db_engine


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_client(engine: Engine, clock: FakeClock) -> Callable[..., TestClient]:
    def make(**overrides: object) -> TestClient:
        settings = Settings(_env_file=None, **{"keys": KEYS, **overrides})  # type: ignore[call-arg]
        return TestClient(create_app(settings=settings, engine=engine, clock=clock))

    return make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()
