"""Returns. Olist has none, so they are generated for a share of delivered orders.

Two kinds of return are generated:

- Undecided cases: a fixed number per open policy rule (window start, campaign items,
  hygiene + defective). Each case touches exactly one open rule, its outcome is split
  between team practices, and it carries an agent_note from NOTE_TEMPLATES.
- Clear cases: everything else. They are kept out of the three undecided zones, so their
  outcome follows from the placeholder policy (v1: window from delivery, v2: window from
  order date, opened hygiene items not returnable) and they carry no note.

NOTE_TEMPLATES is mirrored in mock_api/README.md; the Slack-exceptions corpus uses the
same wording.
"""

import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from mock_api.enums import (
    ItemCondition,
    OrderStatus,
    ReturnReason,
    ReturnResolution,
    ReturnSource,
    ReturnStatus,
)
from mock_api.seed.config import SeedConfig
from mock_api.seed.dates import start_of_day
from mock_api.seed.errors import SeedError
from mock_api.seed.orders import BuiltOrder
from mock_api.seed.rand import rng
from mock_api.seed.rows import OrderItemRow, ProductRow, ReturnItemRow, ReturnRow

NOTE_TEMPLATES: dict[str, str] = {
    "W1": (
        "Requested {days_since_order} days after order but {days_since_delivery} days after "
        "delivery. Approved, counting the window from delivery."
    ),
    "W2": (
        "Requested {days_since_order} days after order. Rejected: outside the 30-day window "
        "from order date (policy v2)."
    ),
    "C1": (
        "Outlet item. Exchange offered instead of a refund, per team practice for campaign items."
    ),
    "C2": "Outlet item. Refund approved: no campaign restriction found in the policy.",
    "C3": "Coupon order ({coupon_code}). Treated as a campaign item: exchange only.",
    "C4": "Coupon order ({coupon_code}). Refund approved: coupon orders are not campaign items.",
    "C5": "Campaign item, changed mind. Return rejected; customer offered store credit.",
    "H1": "Hygiene item opened but defective. Accepted as an exception, see #returns-exceptions.",
    "H2": (
        "Hygiene item opened. Rejected under the opened-packaging rule; defect claim not assessed."
    ),
}
# note id -> (accepted, resolution)
NOTE_OUTCOMES: dict[str, tuple[bool, ReturnResolution | None]] = {
    "W1": (True, ReturnResolution.REFUND),
    "W2": (False, None),
    "C1": (True, ReturnResolution.EXCHANGE),
    "C2": (True, ReturnResolution.REFUND),
    "C3": (True, ReturnResolution.EXCHANGE),
    "C4": (True, ReturnResolution.REFUND),
    "C5": (False, None),
    "H1": (True, ReturnResolution.REFUND),
    "H2": (False, None),
}

REASON_WEIGHTS: dict[ReturnReason, float] = {
    ReturnReason.DEFECTIVE: 0.30,
    ReturnReason.CHANGED_MIND: 0.35,
    ReturnReason.WRONG_ITEM: 0.15,
    ReturnReason.DAMAGED_IN_TRANSIT: 0.20,
}
# Days between delivery and the request, by reason.
REQUEST_DELAY: dict[ReturnReason, tuple[float, float]] = {
    ReturnReason.DAMAGED_IN_TRANSIT: (0, 3),
    ReturnReason.WRONG_ITEM: (0, 7),
    ReturnReason.DEFECTIVE: (1, 30),
    ReturnReason.CHANGED_MIND: (1, 30),
}
REVIEW_WEIGHT: dict[int | None, float] = {1: 6.0, 2: 4.0, 3: 1.5, 4: 0.7, 5: 0.5, None: 1.0}
LATE_REQUEST_SHARE = 0.12  # changed-mind requests made after every possible window
COMMENT_SHARE = 0.7
CUSTOMER_COMMENTS: dict[ReturnReason, tuple[str, ...]] = {
    ReturnReason.DEFECTIVE: (
        "The {item} is faulty.",
        "The {item} stopped working properly after a few days.",
        "The {item} has a manufacturing defect.",
        "Part of the {item} broke on first use.",
    ),
    ReturnReason.CHANGED_MIND: (
        "The {item} does not suit the room.",
        "The colour of the {item} is different from the photos.",
        "Ordered the {item} in two sizes, returning the one that does not fit.",
        "No longer needed.",
    ),
    ReturnReason.WRONG_ITEM: (
        "I received a different {item} from the one I ordered.",
        "Wrong size of {item} delivered.",
        "Wrong colour sent.",
    ),
    ReturnReason.DAMAGED_IN_TRANSIT: (
        "The {item} arrived damaged.",
        "The box was crushed and the {item} is broken.",
        "The {item} was scratched on arrival.",
    ),
}
DECIDED_BEFORE = timedelta(days=5)  # undecided-rule cases are old enough to have an outcome


@dataclass(frozen=True, slots=True)
class ReturnLine:
    item: OrderItemRow
    quantity: int
    condition: ItemCondition


@dataclass(frozen=True, slots=True)
class Case:
    order: BuiltOrder
    lines: list[ReturnLine]
    reason: ReturnReason
    requested_at: datetime
    accepted: bool
    resolution: ReturnResolution | None
    note_id: str | None


@dataclass(frozen=True, slots=True)
class GeneratedReturns:
    returns: list[ReturnRow]
    items: list[ReturnItemRow]
    rules: dict[str, str]  # return id -> undecided rule ("window", "outlet", ...)
    note_ids: dict[str, str]  # return id -> note template id


def _between(r: random.Random, lo: datetime, hi: datetime) -> datetime:
    return (lo + (hi - lo) * r.random()).replace(microsecond=0)


class _Generator:
    def __init__(
        self,
        orders: Sequence[BuiltOrder],
        products: Mapping[str, ProductRow],
        cfg: SeedConfig,
        now: datetime,
    ) -> None:
        self.products = products
        self.cfg = cfg
        self.now = now
        self.window = timedelta(days=cfg.return_window_days)
        self.policy_change = start_of_day(cfg.policy_change)
        self.eligible = [
            o
            for o in orders
            if o.current_status is OrderStatus.DELIVERED
            and o.delivered_at is not None
            and o.delivered_at < now
        ]
        self.used: set[str] = set()

    # Placeholder policy -------------------------------------------------------------

    def is_v2(self, order: BuiltOrder) -> bool:
        return order.order.placed_at >= self.policy_change

    def clear_deadline(self, order: BuiltOrder) -> datetime:
        """Last moment a request is in the window under every reading of the policy."""
        assert order.delivered_at is not None
        if self.is_v2(order):
            return order.order.placed_at + self.window
        return order.delivered_at + self.window

    def product(self, item: OrderItemRow) -> ProductRow:
        return self.products[item.sku]

    # Undecided-rule cases -----------------------------------------------------------

    def _quota(
        self,
        rule: str,
        count: int,
        note_ids: list[str],
        qualifies: Callable[[BuiltOrder], list[OrderItemRow]],
        window: Callable[[BuiltOrder], tuple[datetime, datetime]],
        reason: ReturnReason,
        condition: ItemCondition,
    ) -> list[Case]:
        r = rng(self.cfg.seed, "returns-quota", rule)
        pool: list[tuple[BuiltOrder, list[OrderItemRow], datetime, datetime]] = []
        for order in self.eligible:
            if order.order.id in self.used:
                continue
            lines = qualifies(order)
            if not lines:
                continue
            lo, hi = window(order)
            if hi - lo >= timedelta(hours=12):
                pool.append((order, lines, lo, hi))
        if len(pool) < count:
            raise SeedError(f"Only {len(pool)} orders fit the '{rule}' rule, need {count}.")
        r.shuffle(pool)
        notes = [note_ids[i % len(note_ids)] for i in range(count)]
        r.shuffle(notes)

        cases: list[Case] = []
        for (order, lines, lo, hi), note_id in zip(pool[:count], notes, strict=True):
            item = r.choice(lines)
            accepted, resolution = NOTE_OUTCOMES[note_id]
            self.used.add(order.order.id)
            cases.append(
                Case(
                    order=order,
                    lines=[ReturnLine(item, item.quantity, condition)],
                    reason=reason,
                    requested_at=_between(r, lo, hi),
                    accepted=accepted,
                    resolution=resolution,
                    note_id=note_id,
                )
            )
        return cases

    def _clear_window(self, order: BuiltOrder) -> tuple[datetime, datetime]:
        assert order.delivered_at is not None
        return (
            order.delivered_at + timedelta(hours=6),
            min(self.clear_deadline(order), self.now - DECIDED_BEFORE),
        )

    def _gap_window(self, order: BuiltOrder) -> tuple[datetime, datetime]:
        """After order date + window, but within delivery date + window (rule 1)."""
        assert order.delivered_at is not None
        lo = max(
            order.order.placed_at + self.window + timedelta(days=1),
            order.delivered_at + timedelta(hours=6),
        )
        return lo, min(order.delivered_at + self.window, self.now - DECIDED_BEFORE)

    def _lines_where(self, order: BuiltOrder, *, outlet: bool, hygiene: bool) -> list[OrderItemRow]:
        return [
            i
            for i in order.items
            if self.product(i).is_outlet == outlet and self.product(i).is_hygiene == hygiene
        ]

    def undecided_cases(self) -> dict[str, list[Case]]:
        cfg = self.cfg

        def no_coupon(lines: Callable[[BuiltOrder], list[OrderItemRow]]):
            return lambda o: [] if o.order.coupon_code else lines(o)

        return {
            "hygiene": self._quota(
                "hygiene",
                cfg.quota_hygiene,
                ["H1", "H2"],
                no_coupon(lambda o: self._lines_where(o, outlet=False, hygiene=True)),
                self._clear_window,
                ReturnReason.DEFECTIVE,
                ItemCondition.OPENED,
            ),
            "window": self._quota(
                "window",
                cfg.quota_window,
                ["W1", "W2"],
                no_coupon(
                    lambda o: (
                        self._lines_where(o, outlet=False, hygiene=False) if self.is_v2(o) else []
                    )
                ),
                self._gap_window,
                ReturnReason.CHANGED_MIND,
                ItemCondition.UNOPENED,
            ),
            "outlet": self._quota(
                "outlet",
                cfg.quota_outlet,
                ["C1", "C2", "C5"],
                no_coupon(lambda o: self._lines_where(o, outlet=True, hygiene=False)),
                self._clear_window,
                ReturnReason.CHANGED_MIND,
                ItemCondition.UNOPENED,
            ),
            "coupon": self._quota(
                "coupon",
                cfg.quota_coupon,
                ["C3", "C4", "C5"],
                lambda o: (
                    self._lines_where(o, outlet=False, hygiene=False) if o.order.coupon_code else []
                ),
                self._clear_window,
                ReturnReason.CHANGED_MIND,
                ItemCondition.UNOPENED,
            ),
        }

    # Clear cases --------------------------------------------------------------------

    def clear_case(self, order: BuiltOrder, r: random.Random) -> Case | None:
        """A return whose outcome the placeholder policy decides, or None if none fits."""
        assert order.delivered_at is not None
        delivered = order.delivered_at
        if len(order.items) > 1 and r.random() < 0.15:
            items = list(order.items)
        else:
            items = [r.choice(order.items)]
        products = [self.product(i) for i in items]
        campaign = order.order.coupon_code is not None or any(p.is_outlet for p in products)
        hygiene = any(p.is_hygiene for p in products)

        weights = dict(REASON_WEIGHTS)
        if order.late:
            weights[ReturnReason.DAMAGED_IN_TRANSIT] *= 2.5
        if campaign:
            del weights[ReturnReason.CHANGED_MIND]
        if hygiene:
            del weights[ReturnReason.DEFECTIVE]
        reason = r.choices(list(weights), weights=list(weights.values()))[0]

        # Late requests come after delivery + window, which is past every window reading.
        lo = delivered + self.window + timedelta(days=1)
        hi = min(delivered + self.window + timedelta(days=25), self.now)
        late_request = (
            reason is ReturnReason.CHANGED_MIND and r.random() < LATE_REQUEST_SHARE and hi > lo
        )
        if not late_request:
            min_days, max_days = REQUEST_DELAY[reason]
            hi = min(delivered + timedelta(days=max_days), self.clear_deadline(order), self.now)
            lo = min(delivered + timedelta(days=min_days), hi)
            if hi <= delivered:
                return None

        opened_by_customer = reason is ReturnReason.CHANGED_MIND and r.random() < 0.2
        if reason is ReturnReason.DAMAGED_IN_TRANSIT:
            condition = ItemCondition.DAMAGED
        elif reason is ReturnReason.DEFECTIVE or opened_by_customer:
            condition = ItemCondition.OPENED
        else:
            condition = ItemCondition.UNOPENED

        opened_hygiene = hygiene and condition is ItemCondition.OPENED
        accepted = not late_request and not opened_hygiene
        resolution = None
        if accepted:
            exchange_share = 0.1 if reason is ReturnReason.CHANGED_MIND else 0.25
            resolution = (
                ReturnResolution.EXCHANGE
                if r.random() < exchange_share
                else ReturnResolution.REFUND
            )
        quantities = [i.quantity if r.random() < 0.8 else 1 for i in items]
        return Case(
            order=order,
            lines=[ReturnLine(i, q, condition) for i, q in zip(items, quantities, strict=True)],
            reason=reason,
            requested_at=_between(r, lo, hi),
            accepted=accepted,
            resolution=resolution,
            note_id=None,
        )

    def clear_cases(self, count: int) -> list[Case]:
        """Weighted sample without replacement (Efraimidis-Spirakis keys)."""
        r = rng(self.cfg.seed, "returns-clear")
        keyed: list[tuple[float, str, BuiltOrder]] = []
        for order in self.eligible:
            if order.order.id in self.used:
                continue
            weight = REVIEW_WEIGHT.get(order.review_score, 1.0) * (1.5 if order.late else 1.0)
            keyed.append((r.random() ** (1 / weight), order.order.id, order))
        keyed.sort(key=lambda k: (-k[0], k[1]))

        cases: list[Case] = []
        for _, order_id, order in keyed:
            if len(cases) == count:
                break
            case = self.clear_case(order, rng(self.cfg.seed, "return", order_id))
            if case is not None:
                self.used.add(order_id)
                cases.append(case)
        return cases


def _lifecycle(
    case: Case, now: datetime, r: random.Random
) -> tuple[ReturnStatus, datetime, datetime | None]:
    """(status, updated_at, closed_at) for a case, from its age at 'now'."""
    requested = case.requested_at
    age = now - requested
    if not case.accepted:
        if age < timedelta(days=2) and case.note_id is None:
            return ReturnStatus.REQUESTED, requested, None
        decided = min(requested + timedelta(days=r.uniform(0.5, 2)), now).replace(microsecond=0)
        return ReturnStatus.REJECTED, decided, decided

    approved = requested + timedelta(days=r.uniform(1, 3))
    received = approved + timedelta(days=r.uniform(4, 9))
    closed = received + timedelta(days=r.uniform(2, 6))
    steps = [(approved, ReturnStatus.APPROVED), (received, ReturnStatus.RECEIVED)]
    final = (
        ReturnStatus.EXCHANGED
        if case.resolution is ReturnResolution.EXCHANGE
        else ReturnStatus.REFUNDED
    )
    if closed <= now:
        return final, closed.replace(microsecond=0), closed.replace(microsecond=0)
    for at, status in reversed(steps):
        if at <= now:
            return status, at.replace(microsecond=0), None
    return ReturnStatus.REQUESTED, requested, None


def _note(case: Case) -> str | None:
    if case.note_id is None:
        return None
    assert case.order.delivered_at is not None
    return NOTE_TEMPLATES[case.note_id].format(
        days_since_order=(case.requested_at - case.order.order.placed_at).days,
        days_since_delivery=(case.requested_at - case.order.delivered_at).days,
        coupon_code=case.order.order.coupon_code,
    )


def build_returns(
    orders: Sequence[BuiltOrder],
    products: Mapping[str, ProductRow],
    cfg: SeedConfig,
    now: datetime,
) -> GeneratedReturns:
    """`products` is keyed by SKU."""
    generator = _Generator(orders, products, cfg, now)
    target = math.floor(cfg.return_rate * len(generator.eligible) + 0.5)
    undecided = generator.undecided_cases()
    rule_of: dict[int, str] = {id(c): rule for rule, cases in undecided.items() for c in cases}
    quota_cases = [c for cases in undecided.values() for c in cases]
    cases = quota_cases + generator.clear_cases(max(target - len(quota_cases), 0))
    cases.sort(key=lambda c: (c.requested_at, c.order.order.id))

    returns: list[ReturnRow] = []
    items: list[ReturnItemRow] = []
    rules: dict[str, str] = {}
    note_ids: dict[str, str] = {}
    for number, case in enumerate(cases, start=100001):
        return_id = f"RMA-{number}"
        r = rng(cfg.seed, "return-details", case.order.order.id)
        status, updated_at, closed_at = _lifecycle(case, now, r)
        refund = None
        if status is ReturnStatus.REFUNDED:
            refund = sum((ln.item.unit_price * ln.quantity for ln in case.lines), Decimal(0))
        comment = None
        if r.random() < COMMENT_SHARE:
            item = products[case.lines[0].item.sku].product_type.lower()
            comment = r.choice(CUSTOMER_COMMENTS[case.reason]).format(item=item)
        returns.append(
            ReturnRow(
                id=return_id,
                order_id=case.order.order.id,
                status=status.value,
                reason=case.reason.value,
                resolution=case.resolution.value if case.resolution else None,
                requested_at=case.requested_at,
                updated_at=updated_at,
                closed_at=closed_at,
                refund_amount=refund,
                customer_comment=comment,
                agent_note=_note(case),
                source=(ReturnSource.ADMIN_PANEL if r.random() < 0.65 else ReturnSource.WEB).value,
                api_client=None,
            )
        )
        items.extend(
            ReturnItemRow(
                return_id=return_id,
                order_item_id=ln.item.id,
                quantity=ln.quantity,
                condition=ln.condition.value,
            )
            for ln in case.lines
        )
        if id(case) in rule_of:
            rules[return_id] = rule_of[id(case)]
        if case.note_id is not None:
            note_ids[return_id] = case.note_id
    return GeneratedReturns(returns=returns, items=items, rules=rules, note_ids=note_ids)
