"""The full seed pipeline from Olist data to rows, without touching the database."""

from dataclasses import dataclass
from datetime import datetime

from mock_api.seed.catalog import build_products
from mock_api.seed.config import CATEGORY_MAP, SeedConfig
from mock_api.seed.customers import build_customers
from mock_api.seed.dates import compute_offset, end_of_day
from mock_api.seed.olist import OlistData
from mock_api.seed.orders import BuiltOrder, build_orders
from mock_api.seed.returns import GeneratedReturns, build_returns
from mock_api.seed.rows import CustomerRow, ProductRow, SupplierRow
from mock_api.seed.selection import home_order_ids, sample_by_customer
from mock_api.seed.suppliers import assign_suppliers
from mock_api.seed.transit import adjust_transit


@dataclass(frozen=True, slots=True)
class SeedDataset:
    now: datetime
    offset_days: int
    suppliers: list[SupplierRow]
    products: list[ProductRow]
    customers: list[CustomerRow]
    orders: list[BuiltOrder]
    returns: GeneratedReturns
    transit_changes: dict[str, str]  # order id -> change made by adjust_transit
    lost_parcels: list[str]  # order ids kept in transit as lost parcels


def build_dataset(data: OlistData, cfg: SeedConfig) -> SeedDataset:
    candidates = home_order_ids(data, CATEGORY_MAP)
    selected = sample_by_customer(data, candidates, cfg.target_orders, cfg.seed)

    offset = compute_offset(max(data.orders[o].purchased_at for o in selected), cfg.as_of)
    now = end_of_day(cfg.as_of)

    supplier_of_product, suppliers = assign_suppliers(
        data, CATEGORY_MAP, cfg.supplier_count, cfg.seed
    )
    products = build_products(data, CATEGORY_MAP, supplier_of_product, cfg.seed, cfg.outlet_share)

    first_order_at: dict[str, datetime] = {}
    for order_id in selected:
        olist = data.orders[order_id]
        unique_id = data.customer_unique_ids.get(olist.customer_id, olist.customer_id)
        placed_at = olist.purchased_at + offset
        if unique_id not in first_order_at or placed_at < first_order_at[unique_id]:
            first_order_at[unique_id] = placed_at
    customer_ids, customers = build_customers(first_order_at, cfg.seed)

    orders = build_orders(data, selected, products, customer_ids, offset, now, cfg)
    by_sku = {p.sku: p for p in products.values()}
    returns = build_returns(orders, by_sku, cfg, now)
    # After returns, so orders that have one are never touched.
    transit = adjust_transit(orders, {r.order_id for r in returns.returns}, cfg, now)

    return SeedDataset(
        now=now,
        offset_days=offset.days,
        suppliers=suppliers,
        products=sorted(products.values(), key=lambda p: p.sku),
        customers=customers,
        orders=transit.orders,
        returns=returns,
        transit_changes=transit.changes,
        lost_parcels=transit.lost,
    )
