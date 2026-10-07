"""Checks against the real seed. Local only: they skip without the Olist CSVs."""

import json
import re

import pytest

from lumora_corpus.layout import Layout
from lumora_corpus.manifest import build_manifest, manifest_yaml
from lumora_corpus.policies.build import RenderedDoc
from lumora_corpus.support.build import SupportCorpus, build_support
from lumora_corpus.terms import GLOSSARY, uses
from mock_api.policy import PolicyParams
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset
from mock_api.seed.shipments import FREIGHT_CARRIER

TRACKING_EXAMPLES = ("PCL004417290315", "NP521807364IE", "SLX-KDRW-570214", "HF73019264")


@pytest.fixture(scope="module")
def real_support(real_seed: tuple[SeedDataset, SeedConfig]) -> SupportCorpus:
    ds, cfg = real_seed
    return build_support(ds, cfg.seed, cfg.policy)


def test_committed_support_documents_are_current(
    real_support: SupportCorpus, repo_layout: Layout
) -> None:
    """Regenerate with `make corpus` if this fails."""
    committed = {
        str(p.relative_to(repo_layout.slack)): p.read_bytes()
        for p in repo_layout.slack.rglob("*.json")
    }
    assert committed == real_support.slack.files
    assert (repo_layout.zendesk / "macros.json").read_bytes() == real_support.zendesk["macros.json"]


def test_committed_manifest_is_current(
    real_support: SupportCorpus,
    real_seed: tuple[SeedDataset, SeedConfig],
    policy_docs: dict[str, RenderedDoc],
    repo_layout: Layout,
) -> None:
    ds, cfg = real_seed
    manifest = build_manifest(list(policy_docs.values()), real_support, ds, cfg.policy, cfg.seed)
    assert repo_layout.manifest.read_bytes() == manifest_yaml(manifest)


def test_d4_anchor_is_an_opened_defective_duvet(real_support: SupportCorpus) -> None:
    anchor = real_support.slack.anchor
    assert (anchor.return_id, anchor.order_id) == ("RMA-100151", "LH-1002624")
    assert anchor.product_type == "Duvet" and anchor.note_id == "H1"
    assert "Accept the duvet as an exception" in str(real_support.slack.lead_exception()["text"])


def test_slack_size_and_jargon_counts(real_support: SupportCorpus) -> None:
    texts = [str(m["text"]) for m in real_support.slack.messages]
    assert 60 <= len(texts) <= 100
    macros = json.loads(real_support.zendesk["macros.json"])["macros"]
    macro_texts = [json.dumps(m, ensure_ascii=False) for m in macros]
    for abbreviation in GLOSSARY:
        assert sum(uses(abbreviation, t) for t in texts) >= 3, abbreviation
        assert sum(uses(abbreviation, t) for t in macro_texts) >= 1, abbreviation


def test_every_cited_return_and_order_exists(
    real_support: SupportCorpus, real_seed: tuple[SeedDataset, SeedConfig]
) -> None:
    ds, _ = real_seed
    returns = {r.id: r for r in ds.returns.returns}
    orders = {o.order.id for o in ds.orders}
    texts = [str(m["text"]) for m in real_support.slack.messages]
    macros = json.loads(real_support.zendesk["macros.json"])["macros"]
    texts += [str(m["description"]) for m in macros]
    for text in texts:
        for return_id in re.findall(r"RMA-\d{6}", text):
            assert returns[return_id].agent_note is not None, return_id
        for order_id in re.findall(r"LH-\d{7}", text):
            assert order_id in orders, order_id
        for return_id, order_id in re.findall(r"(RMA-\d{6}) \((LH-\d{7})\)", text):
            assert returns[return_id].order_id == order_id


def test_delivery_ranges_cover_the_seeded_shipments(
    real_seed: tuple[SeedDataset, SeedConfig], policy: PolicyParams
) -> None:
    ds, _ = real_seed
    days: dict[bool, list[float]] = {True: [], False: []}
    for built in ds.orders:
        shipment = built.shipment
        if shipment is None or shipment.delivered_at is None:
            continue
        elapsed = shipment.delivered_at - built.order.placed_at
        days[shipment.carrier == FREIGHT_CARRIER].append(elapsed.total_seconds() / 86400)
    services = ((False, policy.delivery.standard_parcel), (True, policy.delivery.large_item))
    for large, service in services:
        lo, hi = service.typical_days
        inside = sum(lo <= d <= hi for d in days[large])
        assert inside / len(days[large]) >= 0.9, service


def test_tracking_examples_are_not_real_shipments(
    real_seed: tuple[SeedDataset, SeedConfig],
) -> None:
    ds, _ = real_seed
    seeded = {o.shipment.tracking_number for o in ds.orders if o.shipment}
    assert seeded.isdisjoint(TRACKING_EXAMPLES)
