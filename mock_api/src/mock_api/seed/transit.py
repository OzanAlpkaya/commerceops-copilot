"""Which shipments are still in transit at 'now'.

After the date shift, almost every in-transit shipment is an Olist order that was marked
shipped and never delivered. This step, run after returns are generated, reshapes them:

- Legacy DISPATCHED orders stay as they are (old-system leftovers, a data-quality trap).
- A few current-status shipped orders stay in transit as lost parcels, weeks past their
  estimated delivery and spread across ages; the rest are marked delivered close to their
  estimated delivery date.
- Recent delivered orders are put back in transit: most still before their estimated
  delivery, about a third a few days late ("where is my order?" cases).

Orders that have a return are never changed.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from mock_api.enums import OrderStatus, ShipmentStatus
from mock_api.seed.config import SeedConfig
from mock_api.seed.orders import BuiltOrder, stored_status
from mock_api.seed.rand import rng, unit_hash


@dataclass(frozen=True, slots=True)
class TransitResult:
    orders: list[BuiltOrder]
    changes: dict[str, str]  # order id -> "delivered", "recent_on_time" or "recent_late"
    lost: list[str]  # order ids kept in transit as lost parcels


def transit_bucket(order: BuiltOrder, now: datetime, cfg: SeedConfig) -> str:
    """For an order whose shipment is in transit: recent_on_time, recent_late, lost or legacy."""
    shipment = order.shipment
    assert shipment is not None and shipment.status == ShipmentStatus.IN_TRANSIT
    if order.order.status != order.current_status.value:
        return "legacy"
    if order.order.placed_at < now - timedelta(days=cfg.recent_transit_days):
        return "lost"
    eta = shipment.estimated_delivery_at
    return "recent_late" if eta is not None and eta < now else "recent_on_time"


def _spread(items: Sequence[BuiltOrder], k: int) -> list[BuiltOrder]:
    """k items evenly spaced through `items` (oldest to newest), so ages vary."""
    if k >= len(items):
        return list(items)
    if k == 1:
        return [items[len(items) // 2]]
    return [items[round(i * (len(items) - 1) / (k - 1))] for i in range(k)]


def _deliver(order: BuiltOrder, now: datetime, seed: int) -> BuiltOrder:
    shipment = order.shipment
    assert shipment is not None and shipment.shipped_at is not None
    r = rng(seed, "transit-delivered", order.order.id)
    target = shipment.estimated_delivery_at or shipment.shipped_at + timedelta(days=7)
    delivered = target + timedelta(days=r.uniform(-2, 1))
    delivered = min(
        max(delivered, shipment.shipped_at + timedelta(days=1)), now - timedelta(hours=1)
    )
    delivered = delivered.replace(microsecond=0)
    return replace(
        order,
        order=replace(order.order, status=OrderStatus.DELIVERED.value),
        shipment=replace(shipment, status=ShipmentStatus.DELIVERED.value, delivered_at=delivered),
        current_status=OrderStatus.DELIVERED,
        delivered_at=delivered,
    )


def _back_in_transit(order: BuiltOrder, late: bool, now: datetime, cfg: SeedConfig) -> BuiltOrder:
    shipment = order.shipment
    assert shipment is not None and shipment.shipped_at is not None
    r = rng(cfg.seed, "transit-recent", order.order.id)
    if late:
        eta = now - timedelta(days=r.uniform(2, 5))
        eta = max(eta, shipment.shipped_at + timedelta(days=1))
    else:
        eta = shipment.estimated_delivery_at
        if eta is None or eta <= now + timedelta(hours=12):
            eta = now + timedelta(days=r.uniform(1, 6))
    return replace(
        order,
        order=replace(
            order.order,
            status=stored_status("shipped", order.order.placed_at, cfg.legacy_cutoff),
        ),
        shipment=replace(
            shipment,
            status=ShipmentStatus.IN_TRANSIT.value,
            delivered_at=None,
            estimated_delivery_at=eta.replace(microsecond=0),
        ),
        current_status=OrderStatus.SHIPPED,
        delivered_at=None,
    )


def adjust_transit(
    orders: Sequence[BuiltOrder], returned: set[str], cfg: SeedConfig, now: datetime
) -> TransitResult:
    recent_since = now - timedelta(days=cfg.recent_transit_days)
    lost_before = now - timedelta(days=cfg.lost_min_overdue_days)

    def current(o: BuiltOrder, status: OrderStatus) -> bool:
        return (
            o.current_status is status
            and o.order.status == status.value  # current enum, not legacy
            and o.shipment is not None
            and o.order.id not in returned
        )

    stale = [
        o
        for o in orders
        if current(o, OrderStatus.SHIPPED)
        and o.shipment is not None
        and o.shipment.status == ShipmentStatus.IN_TRANSIT
        and o.order.placed_at < recent_since
    ]
    overdue = [
        o
        for o in stale
        if o.shipment is not None
        and o.shipment.estimated_delivery_at is not None
        and o.shipment.estimated_delivery_at <= lost_before
    ]
    lost = {o.order.id for o in _spread(overdue, cfg.lost_parcels)}

    # Recent orders already in transit count toward the target; delivered ones top it up.
    already = [
        o
        for o in orders
        if current(o, OrderStatus.SHIPPED)
        and o.shipment is not None
        and o.shipment.status == ShipmentStatus.IN_TRANSIT
        and o.shipment.shipped_at is not None
        and o.order.placed_at >= recent_since
    ]
    top_up = sorted(
        (
            o
            for o in orders
            if current(o, OrderStatus.DELIVERED)
            and o.order.placed_at >= recent_since
            and o.shipment is not None
            and o.shipment.shipped_at is not None
        ),
        key=lambda o: (-o.order.placed_at.timestamp(), o.order.id),
    )[: max(cfg.recent_transit - len(already), 0)]
    recent = already + top_up
    by_hash = sorted(
        recent, key=lambda o: (unit_hash(cfg.seed, "transit-late", o.order.id), o.order.id)
    )
    late = {o.order.id for o in by_hash[: round(len(recent) * cfg.recent_late_share)]}
    recent_ids = {o.order.id for o in recent}

    adjusted: list[BuiltOrder] = []
    changes: dict[str, str] = {}
    stale_ids = {o.order.id for o in stale}
    for order in orders:
        order_id = order.order.id
        if order_id in stale_ids and order_id not in lost:
            order = _deliver(order, now, cfg.seed)
            changes[order_id] = "delivered"
        elif order_id in recent_ids:
            order = _back_in_transit(order, order_id in late, now, cfg)
            changes[order_id] = "recent_late" if order_id in late else "recent_on_time"
        adjusted.append(order)
    return TransitResult(orders=adjusted, changes=changes, lost=sorted(lost))
