"""The seeded returns that the support documents talk about."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from mock_api.seed.dataset import SeedDataset


@dataclass(frozen=True, slots=True)
class SeedCase:
    return_id: str
    order_id: str
    note_id: str
    agent_note: str
    requested_at: datetime
    decided_at: datetime  # when the return was closed
    product_name: str
    product_type: str
    coupon_code: str | None
    customer_comment: str | None
    days_since_order: int
    days_since_delivery: int


def decided_cases(ds: SeedDataset) -> dict[str, list[SeedCase]]:
    """Seeded returns with an agent_note, by note template id, oldest first."""
    orders = {o.order.id: o for o in ds.orders}
    items = {i.id: i for o in ds.orders for i in o.items}
    products = {p.sku: p for p in ds.products}
    first_item: dict[str, int] = {}
    for line in ds.returns.items:
        first_item.setdefault(line.return_id, line.order_item_id)

    cases: defaultdict[str, list[SeedCase]] = defaultdict(list)
    for ret in ds.returns.returns:
        note_id = ds.returns.note_ids.get(ret.id)
        if note_id is None:
            continue
        assert ret.agent_note is not None and ret.closed_at is not None, ret.id
        built = orders[ret.order_id]
        assert built.delivered_at is not None, ret.id
        product = products[items[first_item[ret.id]].sku]
        cases[note_id].append(
            SeedCase(
                return_id=ret.id,
                order_id=ret.order_id,
                note_id=note_id,
                agent_note=ret.agent_note,
                requested_at=ret.requested_at,
                decided_at=ret.closed_at,
                product_name=product.name,
                product_type=product.product_type,
                coupon_code=built.order.coupon_code,
                customer_comment=ret.customer_comment,
                days_since_order=(ret.requested_at - built.order.placed_at).days,
                days_since_delivery=(ret.requested_at - built.delivered_at).days,
            )
        )
    for group in cases.values():
        group.sort(key=lambda c: (c.requested_at, c.return_id))
    return dict(cases)
