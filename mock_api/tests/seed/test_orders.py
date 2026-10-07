from datetime import UTC, date, datetime, timedelta

from mock_api.enums import LegacyOrderStatus, OrderStatus
from mock_api.seed.config import CATEGORY_MAP, SeedConfig
from mock_api.seed.dataset import SeedDataset
from mock_api.seed.dates import start_of_day
from mock_api.seed.olist import OlistData, OlistOrder
from mock_api.seed.orders import LEGACY_STATUS, effective_status, stored_status
from mock_api.seed.selection import home_order_ids, sample_by_customer

CUTOFF = date(2025, 9, 1)


def test_legacy_enum_before_cutoff_current_enum_after() -> None:
    just_before = start_of_day(CUTOFF) - timedelta(seconds=1)
    assert stored_status("delivered", just_before, CUTOFF) == "COMPLETED"
    assert stored_status("delivered", start_of_day(CUTOFF), CUTOFF) == "delivered"
    assert stored_status("unavailable", just_before, CUTOFF) == "CANCELLED"
    assert stored_status("approved", start_of_day(CUTOFF), CUTOFF) == "processing"


def test_every_olist_status_has_a_legacy_value() -> None:
    assert set(LEGACY_STATUS.values()) == set(LegacyOrderStatus)


def test_future_delivery_means_still_shipped() -> None:
    ts = datetime(2018, 8, 1, tzinfo=UTC)
    olist = OlistOrder("o", "c", "delivered", ts, ts, ts, ts, ts)
    assert effective_status(olist, carrier_at=ts, delivered_at=None) == "shipped"
    assert effective_status(olist, carrier_at=None, delivered_at=None) == "processing"
    assert effective_status(olist, carrier_at=ts, delivered_at=ts) == "delivered"


def test_orders(dataset: SeedDataset, seed_config: SeedConfig) -> None:
    cutoff = start_of_day(seed_config.legacy_cutoff)
    legacy = {s.value for s in LegacyOrderStatus}
    current = {s.value for s in OrderStatus}
    assert len(dataset.orders) == seed_config.target_orders
    for built in dataset.orders:
        o = built.order
        assert o.status in (legacy if o.placed_at < cutoff else current)
        assert o.placed_at <= dataset.now
        assert o.total_amount == o.subtotal + o.shipping_fee - o.discount_amount
        assert (o.coupon_code is None) == (o.discount_amount == 0)
        assert built.delivered_at is None or built.delivered_at <= dataset.now
        if built.current_status is OrderStatus.DELIVERED and built.delivered_at is not None:
            assert built.shipment is not None and built.shipment.status == "delivered"
    assert any(o.order.coupon_code for o in dataset.orders)
    assert any(o.order.status in legacy for o in dataset.orders)


def test_coupon_exactly_on_voucher_orders(
    dataset: SeedDataset, olist_data: OlistData, seed_config: SeedConfig
) -> None:
    selected = sample_by_customer(
        olist_data,
        home_order_ids(olist_data, CATEGORY_MAP),
        seed_config.target_orders,
        seed_config.seed,
    )
    # Lumora order numbers follow purchase time, so the two lists line up.
    ordered = sorted(selected, key=lambda o: (olist_data.orders[o].purchased_at, o))
    for olist_id, built in zip(ordered, dataset.orders, strict=True):
        voucher = any(p.payment_type == "voucher" for p in olist_data.payments.get(olist_id, []))
        assert (built.order.coupon_code is not None) == voucher


def test_tracking_numbers_are_unique(dataset: SeedDataset) -> None:
    numbers = [o.shipment.tracking_number for o in dataset.orders if o.shipment]
    assert len(numbers) == len(set(numbers))
