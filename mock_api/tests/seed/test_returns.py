import random
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from mock_api.enums import ItemCondition, ReturnReason, ReturnStatus
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset
from mock_api.seed.dates import start_of_day
from mock_api.seed.orders import BuiltOrder
from mock_api.seed.returns import NOTE_OUTCOMES, _Generator, return_fee
from mock_api.seed.rows import ProductRow, ReturnItemRow, ReturnRow

OPEN = (ReturnStatus.REQUESTED, ReturnStatus.APPROVED, ReturnStatus.RECEIVED)
CLOSED = (ReturnStatus.REFUNDED, ReturnStatus.EXCHANGED, ReturnStatus.REJECTED)
RULE_ZONE = {"window": "window", "outlet": "campaign", "coupon": "campaign", "hygiene": "hygiene"}


class Ctx:
    def __init__(self, ds: SeedDataset, cfg: SeedConfig) -> None:
        self.cfg = cfg
        self.window = timedelta(days=cfg.return_window_days)
        self.policy_change = start_of_day(cfg.policy_change)
        self.orders: dict[str, BuiltOrder] = {o.order.id: o for o in ds.orders}
        self.products: dict[str, ProductRow] = {p.sku: p for p in ds.products}
        self.skus = {i.id: i.sku for o in ds.orders for i in o.items}
        self.lines: dict[str, list[ReturnItemRow]] = {}
        for item in ds.returns.items:
            self.lines.setdefault(item.return_id, []).append(item)

    def zones(self, ret: ReturnRow) -> set[str]:
        """The undecided policy rules a return touches."""
        built = self.orders[ret.order_id]
        assert built.delivered_at is not None
        placed, delivered = built.order.placed_at, built.delivered_at
        lines = self.lines[ret.id]
        products = [self.products[self.skus[ln.order_item_id]] for ln in lines]
        zones = set()
        is_v2 = placed >= self.policy_change
        if is_v2 and placed + self.window < ret.requested_at <= delivered + self.window:
            zones.add("window")
        if ret.reason == ReturnReason.CHANGED_MIND and (
            built.order.coupon_code or any(p.is_outlet for p in products)
        ):
            zones.add("campaign")
        if ret.reason == ReturnReason.DEFECTIVE and any(
            p.is_hygiene and ln.condition == ItemCondition.OPENED
            for p, ln in zip(products, lines, strict=True)
        ):
            zones.add("hygiene")
        return zones

    def opened_hygiene(self, ret: ReturnRow) -> bool:
        return any(
            self.products[self.skus[ln.order_item_id]].is_hygiene
            and ln.condition == ItemCondition.OPENED
            for ln in self.lines[ret.id]
        )

    def clear_deadline(self, ret: ReturnRow) -> datetime:
        built = self.orders[ret.order_id]
        assert built.delivered_at is not None
        if built.order.placed_at >= self.policy_change:
            return built.order.placed_at + self.window
        return built.delivered_at + self.window


@pytest.fixture(scope="module")
def ctx(dataset: SeedDataset, seed_config: SeedConfig) -> Ctx:
    return Ctx(dataset, seed_config)


def test_quotas_are_met_with_both_outcomes(dataset: SeedDataset, seed_config: SeedConfig) -> None:
    rules = Counter(dataset.returns.rules.values())
    pending = seed_config.open_per_rule
    assert rules == {
        "window": seed_config.quota_window + pending,
        "outlet": seed_config.quota_outlet + pending,
        "coupon": seed_config.quota_coupon + pending,
        "hygiene": seed_config.quota_hygiene + pending,
    }
    by_id = {r.id: r for r in dataset.returns.returns}
    for rule in rules:
        decided = [by_id[rid] for rid, r in dataset.returns.rules.items() if r == rule]
        outcomes = {ret.status == ReturnStatus.REJECTED for ret in decided if ret.agent_note}
        assert outcomes == {True, False}, f"{rule} cases need both outcomes"
        assert all(ret.status in CLOSED for ret in decided if ret.agent_note)


def test_undecided_cases_touch_exactly_their_rule(dataset: SeedDataset, ctx: Ctx) -> None:
    for ret in dataset.returns.returns:
        rule = dataset.returns.rules.get(ret.id)
        if rule is None:
            assert ctx.zones(ret) == set(), f"{ret.id} lands in an undecided zone"
            assert ret.agent_note is None
        else:
            assert ctx.zones(ret) == {RULE_ZONE[rule]}, ret.id
            is_open = ret.id in dataset.returns.open_kinds
            assert (ret.agent_note is None) == is_open, ret.id
            assert ret.agent_note is None or "{" not in ret.agent_note


def test_open_returns_are_undecided(dataset: SeedDataset) -> None:
    for ret in dataset.returns.returns:
        if ret.status in OPEN:
            assert ret.agent_note is None, f"{ret.id} is open but has a decision note"
        if ret.status == ReturnStatus.REQUESTED:
            assert ret.resolution is None, f"{ret.id} is undecided but has a resolution"


def test_targeted_open_returns(dataset: SeedDataset, ctx: Ctx, seed_config: SeedConfig) -> None:
    by_id = {r.id: r for r in dataset.returns.returns}
    kinds = Counter(dataset.returns.open_kinds.values())
    assert kinds == {
        **{rule: seed_config.open_per_rule for rule in RULE_ZONE},
        "eligible": seed_config.open_eligible,
        "ineligible": seed_config.open_ineligible,
        "in_progress": seed_config.open_in_progress,
    }
    for return_id, kind in dataset.returns.open_kinds.items():
        ret = by_id[return_id]
        if kind == "in_progress":
            assert ret.status in (ReturnStatus.APPROVED, ReturnStatus.RECEIVED), return_id
            assert ctx.zones(ret) == set() and ret.requested_at <= ctx.clear_deadline(ret)
            continue
        assert ret.status == ReturnStatus.REQUESTED and ret.resolution is None, return_id
        assert dataset.now - ret.requested_at <= timedelta(hours=36)
        if kind == "eligible":
            assert ctx.zones(ret) == set() and ret.requested_at <= ctx.clear_deadline(ret)
            assert not ctx.opened_hygiene(ret)
        elif kind == "ineligible":
            assert ctx.zones(ret) == set() and ret.requested_at > ctx.clear_deadline(ret)
        else:
            assert ctx.zones(ret) == {RULE_ZONE[kind]}


def test_notes_match_outcomes(dataset: SeedDataset) -> None:
    by_id = {r.id: r for r in dataset.returns.returns}
    for return_id, note_id in dataset.returns.note_ids.items():
        ret = by_id[return_id]
        accepted, resolution = NOTE_OUTCOMES[note_id]
        assert (ret.status == ReturnStatus.REJECTED) == (not accepted)
        assert ret.resolution == (resolution.value if resolution else None)


def test_window_notes_quote_the_real_day_counts(dataset: SeedDataset, ctx: Ctx) -> None:
    for ret in dataset.returns.returns:
        if dataset.returns.note_ids.get(ret.id) in ("W1", "W2"):
            built = ctx.orders[ret.order_id]
            days = (ret.requested_at - built.order.placed_at).days
            assert ret.agent_note is not None
            assert ret.agent_note.startswith(f"Requested {days} days after order")
            assert days > ctx.cfg.return_window_days


def test_clear_outcomes_follow_the_placeholder_policy(dataset: SeedDataset, ctx: Ctx) -> None:
    for ret in dataset.returns.returns:
        if ret.id in dataset.returns.rules or ret.status == ReturnStatus.REQUESTED:
            continue
        too_late = ret.requested_at > ctx.clear_deadline(ret)
        rejected = ret.status == ReturnStatus.REJECTED
        assert rejected == (too_late or ctx.opened_hygiene(ret)), ret.id


def test_return_rows_are_consistent(dataset: SeedDataset, ctx: Ctx) -> None:
    returns = dataset.returns.returns
    delivered = dataset.returns.delivered_orders
    assert abs(len(returns) - ctx.cfg.return_rate * delivered) <= 1
    assert len({r.order_id for r in returns}) == len(returns)
    for ret in returns:
        built = ctx.orders[ret.order_id]
        assert built.delivered_at is not None
        assert built.delivered_at <= ret.requested_at <= ret.updated_at <= dataset.now
        assert ret.requested_at <= dataset.now - timedelta(hours=1), ret.id
        closed = ret.status in (
            ReturnStatus.REFUNDED,
            ReturnStatus.EXCHANGED,
            ReturnStatus.REJECTED,
        )
        assert (ret.closed_at is not None) == closed
        assert (ret.refund_amount is not None) == (ret.status == ReturnStatus.REFUNDED)
        order_items = {i.id: i for i in built.items}
        for line in ctx.lines[ret.id]:
            assert line.order_item_id in order_items
            assert 1 <= line.quantity <= order_items[line.order_item_id].quantity
    assert [r.id for r in returns] == [f"RMA-{100001 + i}" for i in range(len(returns))]


def test_refunds_deduct_the_v2_return_shipping_fee(dataset: SeedDataset, ctx: Ctx) -> None:
    policy = ctx.cfg.policy
    fee = policy.return_fees_eur[ReturnReason.CHANGED_MIND]
    items = {i.id: i for o in dataset.orders for i in o.items}
    deducted: Counter[Decimal] = Counter()
    for ret in dataset.returns.returns:
        if ret.refund_amount is None:
            continue
        lines = [(items[ln.order_item_id], ln.quantity) for ln in ctx.lines[ret.id]]
        goods = sum((item.unit_price * qty for item, qty in lines), Decimal(0))
        is_v2 = ctx.orders[ret.order_id].order.placed_at >= ctx.policy_change
        if is_v2 and ret.reason == ReturnReason.CHANGED_MIND:
            weight = sum((ctx.products[item.sku].weight_g or 0) * qty for item, qty in lines)
            expected = fee.collection if weight > 20_000 else fee.parcel
        else:
            expected = Decimal(0)
        assert ret.refund_amount == max(goods - expected, Decimal(0)), ret.id
        deducted[expected] += 1
    assert deducted[fee.parcel] > 0, "the fixture should exercise the v2 fee"
    assert deducted[Decimal(0)] > 0


def test_collection_fee_for_heavy_returns(dataset: SeedDataset, seed_config: SeedConfig) -> None:
    policy = seed_config.policy
    order = next(
        o for o in dataset.orders if o.order.placed_at >= start_of_day(seed_config.policy_change)
    )
    product = next(p for p in dataset.products)
    heavy = replace(product, weight_g=20_001)
    light = replace(product, weight_g=None)
    fee = policy.return_fees_eur[ReturnReason.CHANGED_MIND]
    assert return_fee(order, ReturnReason.CHANGED_MIND, [(heavy, 1)], policy) == fee.collection
    assert return_fee(order, ReturnReason.CHANGED_MIND, [(light, 3)], policy) == fee.parcel
    assert return_fee(order, ReturnReason.DEFECTIVE, [(heavy, 1)], policy) == 0
    v1_order = next(
        o for o in dataset.orders if o.order.placed_at < start_of_day(seed_config.policy_change)
    )
    assert return_fee(v1_order, ReturnReason.CHANGED_MIND, [(heavy, 1)], policy) == 0


def test_just_delivered_orders_are_not_requested_at_the_as_of_instant(
    dataset: SeedDataset, seed_config: SeedConfig
) -> None:
    template = next(o for o in dataset.orders if o.delivered_at is not None and o.shipment)
    order = replace(
        template,
        order=replace(template.order, placed_at=dataset.now - timedelta(days=3)),
        delivered_at=dataset.now - timedelta(hours=2),
    )
    products = {p.sku: p for p in dataset.products}
    generator = _Generator([order], products, seed_config, dataset.now)

    for i in range(50):
        case = generator.clear_case(order, random.Random(i))
        assert case is not None
        assert order.delivered_at is not None
        assert order.delivered_at <= case.requested_at <= dataset.now - timedelta(hours=1)
