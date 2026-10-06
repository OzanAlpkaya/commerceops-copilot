from collections import Counter
from datetime import timedelta

import pytest

from mock_api.enums import ItemCondition, ReturnReason, ReturnStatus
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset
from mock_api.seed.dates import start_of_day
from mock_api.seed.orders import BuiltOrder
from mock_api.seed.returns import NOTE_OUTCOMES
from mock_api.seed.rows import ProductRow, ReturnItemRow, ReturnRow

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

    def clear_deadline(self, ret: ReturnRow):
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
    assert rules == {
        "window": seed_config.quota_window,
        "outlet": seed_config.quota_outlet,
        "coupon": seed_config.quota_coupon,
        "hygiene": seed_config.quota_hygiene,
    }
    status = {r.id: r.status for r in dataset.returns.returns}
    for rule in rules:
        outcomes = {
            status[rid] == ReturnStatus.REJECTED
            for rid, r in dataset.returns.rules.items()
            if r == rule
        }
        assert outcomes == {True, False}, f"{rule} cases need both outcomes"


def test_undecided_cases_touch_exactly_their_rule(dataset: SeedDataset, ctx: Ctx) -> None:
    for ret in dataset.returns.returns:
        rule = dataset.returns.rules.get(ret.id)
        if rule is None:
            assert ctx.zones(ret) == set(), f"{ret.id} lands in an undecided zone"
            assert ret.agent_note is None
        else:
            assert ctx.zones(ret) == {RULE_ZONE[rule]}, ret.id
            assert ret.agent_note is not None and "{" not in ret.agent_note


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
        lines = ctx.lines[ret.id]
        opened_hygiene = any(
            ctx.products[ctx.skus[ln.order_item_id]].is_hygiene
            and ln.condition == ItemCondition.OPENED
            for ln in lines
        )
        too_late = ret.requested_at > ctx.clear_deadline(ret)
        assert (ret.status == ReturnStatus.REJECTED) == (too_late or opened_hygiene), ret.id


def test_return_rows_are_consistent(dataset: SeedDataset, ctx: Ctx) -> None:
    returns = dataset.returns.returns
    delivered = sum(
        o.delivered_at is not None and o.current_status == "delivered" for o in dataset.orders
    )
    assert abs(len(returns) - ctx.cfg.return_rate * delivered) <= 1
    assert len({r.order_id for r in returns}) == len(returns)
    for ret in returns:
        built = ctx.orders[ret.order_id]
        assert built.delivered_at is not None
        assert built.delivered_at <= ret.requested_at <= ret.updated_at <= dataset.now
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
