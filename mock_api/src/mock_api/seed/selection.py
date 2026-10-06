"""Which Olist orders become Lumora orders."""

from collections import defaultdict
from collections.abc import Mapping

from mock_api.seed.errors import SeedError
from mock_api.seed.olist import OlistData
from mock_api.seed.rand import unit_hash


def home_order_ids(data: OlistData, categories: Mapping[str, str]) -> list[str]:
    """Orders with at least one item where every item is in a mapped category."""
    kept: list[str] = []
    for order_id in sorted(data.orders):
        items = data.items.get(order_id)
        if not items:
            continue
        if all(
            (p := data.products.get(i.product_id)) is not None and p.category in categories
            for i in items
        ):
            kept.append(order_id)
    return kept


def sample_by_customer(data: OlistData, order_ids: list[str], target: int, seed: int) -> list[str]:
    """Pick whole customers in hash order until exactly `target` orders are selected.

    Keeping all orders of a customer preserves repeat-buyer histories. A customer whose
    orders would overshoot the target is skipped, so the result lands on the target unless
    the input runs out.
    """
    by_customer: defaultdict[str, list[str]] = defaultdict(list)
    for order_id in order_ids:
        customer_id = data.orders[order_id].customer_id
        by_customer[data.customer_unique_ids.get(customer_id, customer_id)].append(order_id)

    if len(order_ids) < target:
        raise SeedError(f"Only {len(order_ids)} home orders available, target is {target}.")

    selected: list[str] = []
    for unique_id in sorted(by_customer, key=lambda u: (unit_hash(seed, "customer", u), u)):
        orders = by_customer[unique_id]
        if len(selected) + len(orders) <= target:
            selected.extend(orders)
        if len(selected) == target:
            break
    return sorted(selected)
