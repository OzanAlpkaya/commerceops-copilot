"""Orders, order lines and shipments built from the selected Olist orders."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from mock_api.enums import LegacyOrderStatus, OrderStatus, PaymentMethod, ShipmentStatus
from mock_api.seed.campaigns import campaign_code, coupon_percent
from mock_api.seed.catalog import CENT
from mock_api.seed.config import SeedConfig
from mock_api.seed.dates import past_only, shift, start_of_day
from mock_api.seed.olist import OlistData, OlistItem, OlistOrder
from mock_api.seed.rand import rng
from mock_api.seed.rows import OrderItemRow, OrderRow, ProductRow, ShipmentRow
from mock_api.seed.shipments import choose_carrier, tracking_number

CURRENT_STATUS: dict[str, OrderStatus] = {
    "created": OrderStatus.PENDING,
    "approved": OrderStatus.PROCESSING,
    "invoiced": OrderStatus.PROCESSING,
    "processing": OrderStatus.PROCESSING,
    "shipped": OrderStatus.SHIPPED,
    "delivered": OrderStatus.DELIVERED,
    "canceled": OrderStatus.CANCELED,
    "unavailable": OrderStatus.CANCELED,
}
LEGACY_STATUS: dict[str, LegacyOrderStatus] = {
    "created": LegacyOrderStatus.NEW,
    "approved": LegacyOrderStatus.PAID,
    "invoiced": LegacyOrderStatus.INVOICED,
    "processing": LegacyOrderStatus.PICKING,
    "shipped": LegacyOrderStatus.DISPATCHED,
    "delivered": LegacyOrderStatus.COMPLETED,
    "canceled": LegacyOrderStatus.CANCELLED,
    "unavailable": LegacyOrderStatus.CANCELLED,
}
PAYMENT_METHODS: dict[str, PaymentMethod] = {
    "credit_card": PaymentMethod.CARD,
    "debit_card": PaymentMethod.CARD,
    "boleto": PaymentMethod.BANK_TRANSFER,
}


@dataclass(frozen=True, slots=True)
class BuiltOrder:
    order: OrderRow
    items: list[OrderItemRow]
    shipment: ShipmentRow | None
    current_status: OrderStatus  # the status in the current enum, whatever is stored
    delivered_at: datetime | None
    late: bool
    review_score: int | None


def stored_status(olist_status: str, placed_at: datetime, legacy_cutoff: date) -> str:
    """Orders placed before the v2 go-live keep the legacy status values."""
    if placed_at < start_of_day(legacy_cutoff):
        return LEGACY_STATUS[olist_status].value
    return CURRENT_STATUS[olist_status].value


def effective_status(
    olist: OlistOrder, carrier_at: datetime | None, delivered_at: datetime | None
) -> str:
    """Olist status after the shift: events pushed into the future have not happened yet."""
    if olist.status == "delivered" and olist.delivered_at is not None and delivered_at is None:
        return "shipped" if carrier_at is not None else "processing"
    if olist.status == "shipped" and olist.carrier_at is not None and carrier_at is None:
        return "processing"
    return olist.status


def _lines(items: list[OlistItem]) -> list[tuple[str, int, Decimal, Decimal]]:
    """Collapse Olist's one-row-per-unit into (product_id, quantity, unit_price, freight)."""
    lines: dict[tuple[str, Decimal], tuple[int, Decimal]] = {}
    for item in items:
        quantity, freight = lines.get((item.product_id, item.price), (0, Decimal(0)))
        lines[(item.product_id, item.price)] = (quantity + 1, freight + item.freight)
    return [(pid, qty, price, freight) for (pid, price), (qty, freight) in lines.items()]


def build_orders(
    data: OlistData,
    order_ids: list[str],
    products: Mapping[str, ProductRow],
    customer_ids: Mapping[str, str],
    offset: timedelta,
    now: datetime,
    cfg: SeedConfig,
) -> list[BuiltOrder]:
    ordered = sorted(order_ids, key=lambda o: (data.orders[o].purchased_at, o))
    seen_customers: set[str] = set()
    used_tracking: set[str] = set()
    built: list[BuiltOrder] = []
    next_item_id = 1
    next_shipment = 1

    for number, olist_id in enumerate(ordered, start=1000001):
        olist = data.orders[olist_id]
        order_id = f"LH-{number}"
        unique_id = data.customer_unique_ids.get(olist.customer_id, olist.customer_id)
        first_order = unique_id not in seen_customers
        seen_customers.add(unique_id)

        placed_at = olist.purchased_at + offset
        paid_at = past_only(shift(olist.approved_at, offset), now)
        carrier_at = past_only(shift(olist.carrier_at, offset), now)
        delivered_at = past_only(shift(olist.delivered_at, offset), now)
        estimated_at = shift(olist.estimated_at, offset)
        status = effective_status(olist, carrier_at, delivered_at)
        if delivered_at is not None:
            if carrier_at is None:
                carrier_at = min((paid_at or placed_at) + timedelta(days=1), delivered_at)
            carrier_at = min(carrier_at, delivered_at)

        items: list[OrderItemRow] = []
        weight_g = 0
        for line_no, (product_id, quantity, price, freight) in enumerate(
            _lines(data.items[olist_id]), start=1
        ):
            product = products[product_id]
            weight_g += (product.weight_g or 0) * quantity
            items.append(
                OrderItemRow(
                    id=next_item_id,
                    order_id=order_id,
                    line_no=line_no,
                    sku=product.sku,
                    quantity=quantity,
                    unit_price=price,
                    shipping_fee=freight,
                )
            )
            next_item_id += 1

        subtotal = sum((i.unit_price * i.quantity for i in items), Decimal(0))
        shipping_fee = sum((i.shipping_fee for i in items), Decimal(0))
        payments = data.payments.get(olist_id, [])
        coupon_code = None
        discount = Decimal(0)
        if any(p.payment_type == "voucher" for p in payments):
            coupon_code = campaign_code(placed_at.date(), first_order, cfg.seed, olist_id)
            discount = (subtotal * coupon_percent(coupon_code) / 100).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
        paying = [p for p in payments if p.payment_type != "voucher"]
        main_type = (
            max(paying, key=lambda p: (p.value, -p.sequential)).payment_type if paying else ""
        )
        current = CURRENT_STATUS[status]

        shipment = None
        if carrier_at is not None and current is not OrderStatus.CANCELED:
            carrier = choose_carrier(olist_id, weight_g, cfg.seed)
            tracking_rng = rng(cfg.seed, "tracking", olist_id)
            tracking = tracking_number(carrier, tracking_rng)
            while tracking in used_tracking:
                tracking = tracking_number(carrier, tracking_rng)
            used_tracking.add(tracking)
            shipment = ShipmentRow(
                id=f"SHP-{next_shipment:07d}",
                order_id=order_id,
                carrier=carrier,
                tracking_number=tracking,
                status=(
                    ShipmentStatus.DELIVERED if delivered_at else ShipmentStatus.IN_TRANSIT
                ).value,
                shipped_at=carrier_at,
                estimated_delivery_at=estimated_at,
                delivered_at=delivered_at,
            )
            next_shipment += 1

        built.append(
            BuiltOrder(
                order=OrderRow(
                    id=order_id,
                    customer_id=customer_ids[unique_id],
                    status=stored_status(status, placed_at, cfg.legacy_cutoff),
                    placed_at=placed_at,
                    paid_at=paid_at,
                    currency="EUR",
                    subtotal=subtotal,
                    shipping_fee=shipping_fee,
                    discount_amount=discount,
                    total_amount=subtotal + shipping_fee - discount,
                    coupon_code=coupon_code,
                    payment_method=PAYMENT_METHODS.get(main_type, PaymentMethod.CARD).value,
                ),
                items=items,
                shipment=shipment,
                current_status=current,
                delivered_at=delivered_at,
                late=(
                    olist.delivered_at is not None
                    and olist.estimated_at is not None
                    and olist.delivered_at > olist.estimated_at
                ),
                review_score=data.review_scores.get(olist_id),
            )
        )
    return built
