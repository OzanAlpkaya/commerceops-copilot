import re
from datetime import date

import pytest

from lumora_corpus.layout import Layout
from lumora_corpus.params import date_range, in_words, long_date
from lumora_corpus.policies.build import RenderedDoc, build_policies, campaign_runs
from lumora_corpus.render.pdf_text import find_page, normalise
from mock_api.policy import PolicyParams
from mock_api.seed.campaigns import SEASONAL, WELCOME
from mock_api.seed.catalog import SUBTYPES

POLICIES = (
    "returns-policy-v1",
    "returns-policy-v2",
    "warranty-and-defects",
    "shipping-and-delivery",
)


def _blocks(markdown: str) -> list[str]:
    return [b.strip() for b in markdown.split("\n\n") if b.strip()]


def test_build_is_deterministic(policy: PolicyParams, policy_docs: dict[str, RenderedDoc]) -> None:
    again = {d.name: d for d in build_policies(policy)}
    for name, doc in policy_docs.items():
        assert again[name].pdf == doc.pdf, name
        assert again[name].markdown == doc.markdown, name


def test_committed_documents_are_current(
    repo_layout: Layout, policy_docs: dict[str, RenderedDoc]
) -> None:
    """Regenerate with `make corpus` (or `python -m lumora_corpus policies`) if this fails."""
    assert sorted(p.name for p in repo_layout.policies.iterdir()) == sorted(
        d.pdf_name for d in policy_docs.values()
    )
    for doc in policy_docs.values():
        assert (repo_layout.policies / doc.pdf_name).read_bytes() == doc.pdf, doc.name
        source = repo_layout.policy_sources / f"{doc.name}.md"
        assert source.read_text() == doc.markdown, doc.name


def test_every_markdown_paragraph_is_in_the_pdf(policy_docs: dict[str, RenderedDoc]) -> None:
    for doc in policy_docs.values():
        for block in _blocks(doc.markdown):
            if block.startswith("|"):
                continue  # tables: checked cell by cell in the manifest tests
            for line in block.splitlines():
                text = re.sub(r"^(#+|\d+\.|-)\s+", "", line).replace("**", "")
                assert find_page(doc.pages, text), f"{doc.name}: {text!r}"


def test_policy_page_count(policy_docs: dict[str, RenderedDoc]) -> None:
    assert 8 <= sum(len(policy_docs[n].pages) for n in POLICIES) <= 12


def test_d1_versions_differ_only_where_intended(
    policy: PolicyParams, policy_docs: dict[str, RenderedDoc]
) -> None:
    v1 = _blocks(policy_docs["returns-policy-v1"].markdown)
    v2 = _blocks(policy_docs["returns-policy-v2"].markdown)
    only_v1 = [b for b in v1 if b not in v2]
    only_v2 = [b for b in v2 if b not in v1]
    assert only_v1[0] == "Superseded"
    assert v1[1] == v2[0] == "# Returns Policy"
    assert len(only_v1) == 4 and len(only_v2) == 5, (only_v1, only_v2)
    assert f"This policy applies to orders placed on or after {long_date(date(2026, 3, 1))}." in (
        only_v2
    )
    shared = [b for b in v2 if b in v1]
    assert len(shared) / len(v2) >= 0.8
    assert "Superseded" not in policy_docs["returns-policy-v2"].markdown


def test_d2_two_window_clauses_in_v2(policy_docs: dict[str, RenderedDoc]) -> None:
    v2 = policy_docs["returns-policy-v2"]
    order_clause = "You can return items within 30 days of the order date."
    receipt_clause = "Send the item back within 30 days of receiving it."
    assert find_page(v2.pages, order_clause) and find_page(v2.pages, receipt_clause)
    section_2 = v2.markdown.split("## 2.")[1].split("## 3.")[0]
    section_6 = v2.markdown.split("## 6.")[1].split("## 7.")[0]
    assert order_clause in section_2 and receipt_clause in section_6
    assert "within 30 days of delivery" in policy_docs["returns-policy-v1"].markdown


def test_d3_campaign_item_is_never_defined(policy_docs: dict[str, RenderedDoc]) -> None:
    definition = re.compile(
        r"campaign items?\s+(is|are|means?|includes?|refers?|covers?)\b|"
        r"(is|are|counts? as|treated as)\s+(a\s+)?campaign items?|campaign items?\s*\(",
        re.IGNORECASE,
    )
    for doc in policy_docs.values():
        assert not definition.search(normalise(doc.markdown)), doc.name
    v2 = policy_docs["returns-policy-v2"].markdown
    assert "Campaign items can be exchanged but not refunded." in v2
    assert (
        "Outlet items are sold at reduced prices." in policy_docs["shipping-and-delivery"].markdown
    )
    assert "Spring campaign: SPRING15" in policy_docs["promo-codes-2026"].markdown


def test_d4_hygiene_rule_covers_every_seeded_hygiene_type(
    policy_docs: dict[str, RenderedDoc],
) -> None:
    words = {
        "Pillowcase Pair": "bedding",
        "Hand Towel": "towels",
        "Bath Towel": "towels",
        "Fitted Sheet": "bedding",
        "Pillow": "pillows",
        "Mattress Protector": "mattress protectors",
        "Sheet Set": "bedding",
        "Duvet Cover Set": "bedding",
        "Bathrobe": "bathrobes",
        "Duvet": "bedding",
        "Weighted Blanket": "weighted blankets",
        "Mattress Topper": "mattress toppers",
        "Mattress": "mattresses",
    }
    hygiene = {s.label for subtypes in SUBTYPES.values() for s in subtypes if s.hygiene}
    assert hygiene == set(words)
    for name in ("returns-policy-v1", "returns-policy-v2"):
        section = policy_docs[name].markdown.split("### 5.1")[1].split("### 5.2")[0]
        assert (
            "Opened pillows, bedding, mattresses and mattress protectors cannot be returned "
            "for hygiene reasons." in section
        )
        assert all(word in section for word in words.values())
    warranty = policy_docs["warranty-and-defects"].markdown
    assert (
        "Defective items can be returned for a replacement or refund within 30 days of delivery."
        in warranty
    )
    assert "hygiene" not in warranty.lower()


def test_d5_promo_codes_match_the_seed_calendar(policy_docs: dict[str, RenderedDoc]) -> None:
    promo = policy_docs["promo-codes-2026"]
    current, previous = campaign_runs(2026)
    assert {r.code for r in current} == {c.code for c in SEASONAL}
    for run in current:
        terms = f"{run.code}: {run.percent}% off your order, {run.dates}, cannot be combined with "
        assert find_page(promo.pages, terms + f"{WELCOME.code}."), run.code
    for run in current + previous:
        assert f"| {run.code} | {run.percent}% | {run.dates} |" in promo.markdown
    assert (
        "BOXING25: 25% off your order, 25 December 2025 – 6 January 2026, cannot be combined "
        "with WELCOME10." in promo.markdown
    )
    calendar = [r.code for r in current]
    assert calendar[-3:] == ["BF25", "XMAS15", "BOXING25"]


def test_d6_and_d7_shipping_tables(
    policy: PolicyParams, policy_docs: dict[str, RenderedDoc]
) -> None:
    shipping = policy_docs["shipping-and-delivery"]
    md = shipping.markdown
    assert "| Change of mind | €4.95 | €29.00 |" in md
    for reason in ("Defective item", "Wrong item sent", "Damaged in transit"):
        assert f"| {reason} | Free | Free |" in md
    for carrier in ("Parcelo", "NordPost", "SwiftLane Express"):
        assert f"| Standard parcel | {carrier} | Tracked parcel | 2–30 days after the order |" in md
    assert "| Large item (over 20 kg) | Hollis Freight | Two-person delivery | 3–40 days" in md
    assert "The estimated delivery date on your order confirmation is the one to rely on." in md
    assert "Report damage within 7 days of delivery, with photos" in md
    for name in ("returns-policy-v1", "returns-policy-v2"):
        assert "See Shipping & Delivery Policy §4." in policy_docs[name].markdown


FORBIDDEN = (
    # D10: topics deliberately absent.
    "price match",
    "price-match",
    "gift",
    "outside ireland",
    "international",
    "abroad",
    "overseas",
    "northern ireland",
    "united kingdom",
    "extended warranty",
    "warranty extension",
    "extend your warranty",
    # Statutory periods that would resolve D4 or contradict the 30-day rules.
    "2-year",
    "two-year",
    "2 years",
    "two years",
    "legal guarantee",
    "14 days",
    "14-day",
    "fourteen days",
    "withdrawal",
    "cooling-off",
    "cooling off",
)


@pytest.mark.parametrize("term", FORBIDDEN)
def test_d10_forbidden_terms_are_absent(term: str, policy_docs: dict[str, RenderedDoc]) -> None:
    for doc in policy_docs.values():
        assert term not in doc.markdown.lower(), doc.name
        assert term not in normalise(" ".join(doc.pages)).lower(), doc.name


def test_warranty_mentions_only_generic_statutory_rights(
    policy_docs: dict[str, RenderedDoc],
) -> None:
    warranty = policy_docs["warranty-and-defects"].markdown
    section_1 = warranty.split("## 1.")[1].split("## 2.")[0]
    assert _blocks(section_1)[1:] == ["This policy does not affect your statutory rights."]


def test_formatting_helpers() -> None:
    assert in_words(14) == "two weeks"
    assert in_words(10) == "10 days"
    assert date_range(date(2026, 3, 1), date(2026, 5, 31)) == "1 March – 31 May 2026"
    assert date_range(date(2025, 12, 25), date(2026, 1, 6)) == ("25 December 2025 – 6 January 2026")
