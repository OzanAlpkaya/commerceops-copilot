from collections import defaultdict

from mock_api.seed.config import CATEGORY_MAP
from mock_api.seed.olist import OlistData
from mock_api.seed.selection import home_order_ids, sample_by_customer


def test_home_orders_have_only_home_items(olist_data: OlistData) -> None:
    kept = home_order_ids(olist_data, CATEGORY_MAP)

    for order_id in kept:
        categories = {
            olist_data.products[i.product_id].category for i in olist_data.items[order_id]
        }
        assert categories <= CATEGORY_MAP.keys()
    excluded = set(olist_data.orders) - set(kept)
    assert any(o not in olist_data.items for o in excluded), "orders without items are dropped"
    assert any(
        "beleza_saude" in {olist_data.products[i.product_id].category for i in olist_data.items[o]}
        for o in excluded
        if o in olist_data.items
    ), "orders with a non-home item are dropped"


def test_sample_hits_target_with_whole_customers(olist_data: OlistData) -> None:
    kept = home_order_ids(olist_data, CATEGORY_MAP)

    sample = sample_by_customer(olist_data, kept, 200, seed=1)

    assert len(sample) == 200
    by_customer: defaultdict[str, set[str]] = defaultdict(set)
    for order_id in kept:
        customer = olist_data.customer_unique_ids[olist_data.orders[order_id].customer_id]
        by_customer[customer].add(order_id)
    chosen = set(sample)
    for orders in by_customer.values():
        assert orders <= chosen or not orders & chosen


def test_sample_is_deterministic_per_seed(olist_data: OlistData) -> None:
    kept = home_order_ids(olist_data, CATEGORY_MAP)

    assert sample_by_customer(olist_data, kept, 150, 1) == sample_by_customer(
        olist_data, kept, 150, 1
    )
    assert sample_by_customer(olist_data, kept, 150, 1) != sample_by_customer(
        olist_data, kept, 150, 2
    )
