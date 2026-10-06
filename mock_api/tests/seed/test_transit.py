from collections import Counter
from datetime import timedelta

from mock_api.enums import OrderStatus, ShipmentStatus
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset
from mock_api.seed.transit import adjust_transit, transit_bucket


def _in_transit(ds: SeedDataset):
    return [
        o
        for o in ds.orders
        if o.shipment is not None and o.shipment.status == ShipmentStatus.IN_TRANSIT
    ]


def test_orders_with_a_return_are_never_changed(dataset: SeedDataset) -> None:
    returned = {r.order_id for r in dataset.returns.returns}
    assert dataset.transit_changes
    assert not returned & dataset.transit_changes.keys()
    by_id = {o.order.id: o for o in dataset.orders}
    for order_id in returned:
        built = by_id[order_id]
        assert built.current_status is OrderStatus.DELIVERED and built.delivered_at is not None


def test_guard_skips_every_returned_order(dataset: SeedDataset, seed_config: SeedConfig) -> None:
    every_order = {o.order.id for o in dataset.orders}

    result = adjust_transit(dataset.orders, every_order, seed_config, dataset.now)

    assert result.changes == {}
    assert result.orders == dataset.orders


def test_in_transit_buckets(dataset: SeedDataset, seed_config: SeedConfig) -> None:
    buckets = Counter(transit_bucket(o, dataset.now, seed_config) for o in _in_transit(dataset))
    changes = Counter(dataset.transit_changes.values())

    assert buckets["lost"] == len(dataset.lost_parcels) == seed_config.lost_parcels
    assert buckets["recent_on_time"] == changes["recent_on_time"]
    assert buckets["recent_late"] == changes["recent_late"]
    recent = changes["recent_on_time"] + changes["recent_late"]
    assert recent == seed_config.recent_transit
    assert changes["recent_late"] == round(recent * seed_config.recent_late_share)


def test_in_transit_orders_look_right(dataset: SeedDataset, seed_config: SeedConfig) -> None:
    recent_since = dataset.now - timedelta(days=seed_config.recent_transit_days)
    lost_before = dataset.now - timedelta(days=seed_config.lost_min_overdue_days)
    for o in _in_transit(dataset):
        assert o.shipment is not None
        eta = o.shipment.estimated_delivery_at
        assert o.delivered_at is None and o.shipment.delivered_at is None
        bucket = transit_bucket(o, dataset.now, seed_config)
        if bucket == "legacy":
            assert o.order.status == "DISPATCHED"
            continue
        assert o.order.status == "shipped" and o.current_status is OrderStatus.SHIPPED
        if bucket == "lost":
            assert eta is not None and eta <= lost_before
        else:
            assert o.order.placed_at >= recent_since
            assert eta is not None and o.shipment.shipped_at is not None
            assert o.shipment.shipped_at < eta
            if bucket == "recent_late":
                assert dataset.now - timedelta(days=5) <= eta < dataset.now
            else:
                assert eta > dataset.now


def test_stale_shipments_are_delivered_near_their_eta(dataset: SeedDataset) -> None:
    by_id = {o.order.id: o for o in dataset.orders}
    delivered = [by_id[i] for i, c in dataset.transit_changes.items() if c == "delivered"]
    assert delivered
    for o in delivered:
        assert o.shipment is not None and o.shipment.shipped_at is not None
        assert o.order.status == "delivered" and o.shipment.status == "delivered"
        assert o.delivered_at == o.shipment.delivered_at
        assert o.delivered_at is not None
        assert o.shipment.shipped_at < o.delivered_at <= dataset.now
        eta = o.shipment.estimated_delivery_at
        if eta is not None and eta + timedelta(days=1) < dataset.now:
            assert abs(o.delivered_at - eta) <= timedelta(days=2)


def test_current_status_shipped_means_in_transit(dataset: SeedDataset) -> None:
    for o in dataset.orders:
        if o.order.status == "shipped":
            assert o.shipment is not None and o.shipment.status == "in_transit"
