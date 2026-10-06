"""Human-readable summary of a SeedDataset."""

from collections import Counter
from collections.abc import Mapping

from mock_api.enums import OrderStatus
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset
from mock_api.seed.dates import start_of_day


def _pct(part: int, whole: int) -> str:
    return f"{part:,} ({part / whole:.1%})" if whole else f"{part:,}"


def _counter(counter: Counter[str]) -> str:
    return ", ".join(
        f"{k} {v:,}" for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    )


def summarize(ds: SeedDataset, cfg: SeedConfig, checksums: Mapping[str, str] | None = None) -> str:
    orders = [o.order for o in ds.orders]
    n_orders = len(orders)
    products = {p.sku: p for p in ds.products}
    policy_change = start_of_day(cfg.policy_change)
    legacy_cutoff = start_of_day(cfg.legacy_cutoff)

    post = sum(o.placed_at >= policy_change for o in orders)
    legacy = sum(o.placed_at < legacy_cutoff for o in orders)
    delivered = sum(o.current_status is OrderStatus.DELIVERED for o in ds.orders)
    coupons = Counter(o.coupon_code for o in orders if o.coupon_code)
    with_outlet = sum(any(products[i.sku].is_outlet for i in o.items) for o in ds.orders)
    with_hygiene = sum(any(products[i.sku].is_hygiene for i in o.items) for o in ds.orders)
    shipments = [o.shipment for o in ds.orders if o.shipment is not None]
    customers_with_orders = Counter(o.customer_id for o in orders)
    returns = ds.returns.returns

    n_products = len(ds.products)
    hygiene = sum(p.is_hygiene for p in ds.products)
    outlet = sum(p.is_outlet for p in ds.products)
    weeks = ds.offset_days // 7

    lines = [
        f"As-of date        {cfg.as_of}  (offset {ds.offset_days} days = {weeks} weeks)",
        f"Order dates       {min(o.placed_at for o in orders):%Y-%m-%d} .. "
        f"{max(o.placed_at for o in orders):%Y-%m-%d}",
        "",
        f"Suppliers         {len(ds.suppliers):,}",
        f"Products          {n_products:,}  hygiene {_pct(hygiene, n_products)}, "
        f"outlet {_pct(outlet, n_products)}",
        f"Customers         {len(ds.customers):,}  repeat buyers "
        f"{sum(c > 1 for c in customers_with_orders.values()):,}",
        f"Orders            {n_orders:,}  items {sum(len(o.items) for o in ds.orders):,}",
        f"  before {cfg.policy_change} (policy v1)   {_pct(n_orders - post, n_orders)}",
        f"  from {cfg.policy_change} (policy v2)     {_pct(post, n_orders)}",
        f"  legacy status (before {cfg.legacy_cutoff}) {_pct(legacy, n_orders)}",
        f"  stored status     {_counter(Counter(o.status for o in orders))}",
        f"  with coupon       {_pct(sum(coupons.values()), n_orders)}: {_counter(coupons)}",
        f"  with outlet item  {_pct(with_outlet, n_orders)}",
        f"  with hygiene item {_pct(with_hygiene, n_orders)}",
        f"Shipments         {len(shipments):,}  {_counter(Counter(s.carrier for s in shipments))}",
        f"  status            {_counter(Counter(s.status for s in shipments))}",
        f"Returns           {len(returns):,} = {len(returns) / delivered:.1%} "
        f"of {delivered:,} delivered orders",
        f"  reason            {_counter(Counter(r.reason for r in returns))}",
        f"  status            {_counter(Counter(r.status for r in returns))}",
        f"  undecided rules   {_counter(Counter(ds.returns.rules.values()))}",
        f"  note templates    {_counter(Counter(ds.returns.note_ids.values()))}",
    ]
    if checksums is not None:
        lines += ["", "Table checksums (md5)"]
        lines += [f"  {name:<14} {value}" for name, value in checksums.items()]
    return "\n".join(lines)
