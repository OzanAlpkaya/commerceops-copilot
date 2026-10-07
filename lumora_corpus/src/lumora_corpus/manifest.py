"""data/ground_truth/corpus_manifest.yaml: where each deliberate difficulty lives.

Week 2 evals target these entries, so every location is checked against the generated
documents when the manifest is built: the text must be in the Markdown source and on the
stated PDF page, or in the stated Slack message or Zendesk macro.
"""

import json
from datetime import UTC, datetime
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from lumora_corpus.params import eur, long_date
from lumora_corpus.policies.build import RenderedDoc
from lumora_corpus.render.pdf_text import find_page, normalise
from lumora_corpus.support.build import SupportCorpus
from lumora_corpus.support.slack import CHANNEL_NAME
from lumora_corpus.support.zendesk import CHANGED_MIND
from lumora_corpus.terms import ABSENT_TOPICS, FORBIDDEN, GLOSSARY, uses
from mock_api.enums import ReturnReason
from mock_api.policy import PolicyParams
from mock_api.seed.dataset import SeedDataset


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Location(_Model):
    document: str  # path under data/corpus/
    section: str
    kind: Literal["text", "table_row", "slack_message", "zendesk_macro"] = "text"
    text: str  # exact text; a Markdown table row for kind "table_row"
    page: int | None = None  # PDFs
    ts: str | None = None  # Slack messages
    macro_id: int | None = None  # Zendesk macros


class Difficulty(_Model):
    id: str
    title: str
    undecided_rule: int | None = None  # the discovery summary's open policy rules (1-3)
    tests: str
    expected_behaviour: str
    locations: list[Location] = []
    seed_refs: list[str] = []  # seeded returns and orders the difficulty applies to
    glossary: dict[str, str] | None = None
    absent_topics: list[str] | None = None
    forbidden_terms: list[str] | None = None


class Manifest(_Model):
    corpus: str
    policy_params: str
    seed: int
    as_of: str
    difficulties: list[Difficulty]


def table_cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


class _Locator:
    def __init__(self, docs: list[RenderedDoc], support: SupportCorpus) -> None:
        self.docs = {d.name: d for d in docs}
        self.slack = support.slack
        self.macros: list[dict[str, object]] = json.loads(support.zendesk["macros.json"])["macros"]

    def pdf(self, name: str, section: str, text: str) -> Location:
        doc = self.docs[name]
        if text not in doc.markdown:
            raise ValueError(f"{name}: not in the Markdown source: {text!r}")
        page = find_page(doc.pages, text)
        if page is None:
            raise ValueError(f"{name}: not in the PDF text: {text!r}")
        return Location(document=f"policies/{doc.pdf_name}", section=section, text=text, page=page)

    def row(self, name: str, section: str, row: str) -> Location:
        doc = self.docs[name]
        if row not in doc.markdown:
            raise ValueError(f"{name}: table row not in the Markdown source: {row!r}")
        cells = [normalise(c) for c in table_cells(row)]
        pages = [n for n, p in enumerate(doc.pages, 1) if all(c in normalise(p) for c in cells)]
        if not pages:
            raise ValueError(f"{name}: table row cells not on one PDF page: {row!r}")
        return Location(
            document=f"policies/{doc.pdf_name}",
            section=section,
            kind="table_row",
            text=row,
            page=pages[0],
        )

    def slack_message(self, message: dict[str, object], section: str) -> Location:
        ts = str(message["ts"])
        day = self._day(ts)
        return Location(
            document=f"slack/returns-exceptions/{CHANNEL_NAME}/{day}.json",
            section=section,
            kind="slack_message",
            text=str(message["text"]),
            ts=ts,
        )

    def macro(self, title: str, text: str) -> Location:
        macro = next(m for m in self.macros if m["title"] == title)
        if text not in json.dumps(macro, ensure_ascii=False):
            raise ValueError(f"Macro {title!r} does not contain {text!r}")
        macro_id = macro["id"]
        assert isinstance(macro_id, int)
        return Location(
            document="zendesk/macros.json",
            section=title,
            kind="zendesk_macro",
            text=text,
            macro_id=macro_id,
        )

    def first_macro_using(self, abbreviation: str) -> Location:
        for macro in self.macros:
            for field in ("title", "description"):
                value = str(macro[field])
                if uses(abbreviation, value):
                    return self.macro(str(macro["title"]), value)
            actions = macro["actions"]
            assert isinstance(actions, list)
            html = str(actions[0]["value"])
            if uses(abbreviation, html):
                sentence = next(s for s in html.split("</p>") if uses(abbreviation, s))
                return self.macro(str(macro["title"]), sentence.removeprefix("<p>"))
        raise ValueError(f"No macro uses {abbreviation}")

    def first_message_using(self, abbreviation: str) -> dict[str, object]:
        return next(m for m in self.slack.messages if uses(abbreviation, str(m["text"])))

    def thread(self, key: str) -> list[dict[str, object]]:
        return [m for m in self.slack.messages if self.slack.thread_keys[str(m["ts"])] == key]

    @staticmethod
    def _day(ts: str) -> str:
        return datetime.fromtimestamp(float(ts), UTC).date().isoformat()


def build_manifest(
    docs: list[RenderedDoc],
    support: SupportCorpus,
    ds: SeedDataset,
    policy: PolicyParams,
    seed: int,
) -> Manifest:
    at = _Locator(docs, support)
    v1, v2 = policy.versions.v1, policy.versions.v2
    v2_from = long_date(v2.orders_from)
    fee = policy.return_fees_eur
    open_by_rule: dict[str, list[str]] = {}
    for return_id, kind in sorted(ds.returns.open_kinds.items()):
        open_by_rule.setdefault(kind, []).append(return_id)
    anchor = support.slack.anchor
    h2_keys = sorted({k for k in support.slack.thread_keys.values() if k.startswith("H2:")})
    h2_parent = at.thread(h2_keys[0])[0]
    window_order = f"You can return items within {v2.window_days} days of the order date."
    window_receipt = f"Send the item back within {v1.window_days} days of receiving it."
    hygiene = (
        "Opened pillows, bedding, mattresses and mattress protectors cannot be returned for "
        "hygiene reasons."
    )
    changed_mind = fee[ReturnReason.CHANGED_MIND]

    difficulties = [
        Difficulty(
            id="D1",
            title="Two policy versions",
            tests="Version selection by order date, near-duplicate retrieval, reranking, "
            "version metadata on chunks.",
            expected_behaviour="Answers from the version in force on the order date and names "
            "that version. If no order is given, states both rules and asks for the order.",
            locations=[
                at.pdf("returns-policy-v1", "Header", "Superseded"),
                at.pdf(
                    "returns-policy-v1",
                    "§2 Return window",
                    f"You can return items within {v1.window_days} days of delivery.",
                ),
                at.pdf(
                    "returns-policy-v2",
                    "§1 Scope",
                    f"This policy applies to orders placed on or after {v2_from}.",
                ),
                at.pdf("returns-policy-v2", "§2 Return window", window_order),
            ],
        ),
        Difficulty(
            id="D2",
            title="Return window start contradicts itself",
            undecided_rule=1,
            tests="Retrieving both conflicting passages, faithfulness, noticing a contradiction.",
            expected_behaviour="If both readings give the same answer, answers normally. If the "
            "request is more than 30 days after the order but within 30 days of delivery, does "
            "not decide: quotes both clauses and escalates to the team lead.",
            locations=[
                at.pdf("returns-policy-v2", "§2 Return window", window_order),
                at.pdf("returns-policy-v2", "§6 How to return", window_receipt),
            ],
            seed_refs=open_by_rule.get("window", []),
        ),
        Difficulty(
            id="D3",
            title='"Campaign item" is never defined',
            undecided_rule=2,
            tests="Not inventing a definition from suggestive wording.",
            expected_behaviour="For an order with an outlet item or a coupon, states the rule, "
            'says that "campaign item" is not defined, and escalates. For an order with '
            "neither, applies the normal rule.",
            locations=[
                at.pdf(
                    "returns-policy-v2",
                    "§4 Refunds and exchanges",
                    "Campaign items can be exchanged but not refunded.",
                ),
                at.pdf("promo-codes-2026", "§3 Terms by campaign", "Spring campaign: SPRING15"),
                at.pdf(
                    "promo-codes-2026",
                    "§1 How campaign codes work",
                    "Campaign codes give a percentage off the items in your order.",
                ),
                at.pdf(
                    "shipping-and-delivery", "§7 Outlet", "Outlet items are sold at reduced prices."
                ),
            ],
            seed_refs=open_by_rule.get("outlet", []) + open_by_rule.get("coupon", []),
        ),
        Difficulty(
            id="D4",
            title="Hygiene exception exists only in Slack",
            undecided_rule=3,
            tests="Conflicting rules across documents; source authority (Slack records "
            "practice, not policy).",
            expected_behaviour="States both written rules, mentions the Slack practice as "
            "informal, flags the case as undecided, and escalates.",
            locations=[
                at.pdf("returns-policy-v1", "§5.1 Hygiene items", hygiene),
                at.pdf("returns-policy-v2", "§5.1 Hygiene items", hygiene),
                at.pdf(
                    "warranty-and-defects",
                    "§2 Defective items",
                    "Defective items can be returned for a replacement or refund within "
                    f"{policy.claims.defective_days} days of delivery.",
                ),
                at.slack_message(
                    support.slack.lead_exception(), f"Team lead's exception on {anchor.return_id}"
                ),
                at.slack_message(h2_parent, f"Opposite decision on {h2_keys[0].split(':')[1]}"),
            ],
            seed_refs=[anchor.return_id, anchor.order_id, *open_by_rule.get("hygiene", [])],
        ),
        Difficulty(
            id="D5",
            title="Exact identifiers",
            tests="Keyword search; the case for hybrid search over vector-only search.",
            expected_behaviour="Retrieves the passage with the exact code or SKU and never "
            "answers from a similar one. Supplier SKUs: see the supplier ground truth.",
            locations=[
                at.pdf(
                    "promo-codes-2026",
                    "§3 Terms by campaign",
                    "BOXING25: 25% off your order, 25 December 2025 – 6 January 2026, cannot be "
                    "combined with WELCOME10.",
                ),
                at.row(
                    "promo-codes-2026",
                    "§2 Calendar for 2026",
                    "| Black Friday campaign | BF25 | 25% | 20 November – 2 December 2026 |",
                ),
                at.row(
                    "promo-codes-2026",
                    "§2 Calendar for 2026",
                    "| Christmas campaign | XMAS15 | 15% | 3 December – 24 December 2026 |",
                ),
                at.pdf(
                    "shipping-and-delivery",
                    "§8 Tracking",
                    "SwiftLane Express: SLX, four letters and six digits",
                ),
            ],
        ),
        Difficulty(
            id="D6",
            title="Answer inside a table",
            tests="Table-aware chunking; keeping header rows with their values.",
            expected_behaviour="Gives the exact figure and cites the table.",
            locations=[
                at.row(
                    "shipping-and-delivery",
                    "§5 Return shipping costs",
                    f"| Change of mind | {eur(changed_mind.parcel)} | "
                    f"{eur(changed_mind.collection)} |",
                ),
                at.row(
                    "shipping-and-delivery",
                    "§5 Return shipping costs",
                    "| Defective item | Free | Free |",
                ),
                at.pdf(
                    "shipping-and-delivery",
                    "§5 Return shipping costs",
                    f"These costs apply to orders placed on or after {v2_from}.",
                ),
                at.row(
                    "shipping-and-delivery",
                    "§3 Delivery options",
                    next(
                        line
                        for line in at.docs["shipping-and-delivery"].markdown.splitlines()
                        if line.startswith("| Large item")
                    ),
                ),
            ],
        ),
        Difficulty(
            id="D7",
            title="Cross-reference between documents",
            tests="Multi-hop retrieval.",
            expected_behaviour="Combines both passages and cites both documents.",
            locations=[
                at.pdf(
                    "returns-policy-v2", "§5.2 Damaged items", "See Shipping & Delivery Policy §4."
                ),
                at.pdf(
                    "shipping-and-delivery",
                    "§4 Damaged or missing deliveries",
                    f"Report damage within {policy.claims.damaged_report_days} days of delivery, "
                    "with photos of the item and its packaging.",
                ),
            ],
        ),
        Difficulty(
            id="D8",
            title="Outdated Zendesk macro",
            tests="Source priority: policy over macro.",
            expected_behaviour="Follows policy v2 and points out that the macro is outdated.",
            locations=[
                at.macro(
                    CHANGED_MIND,
                    f"You can send it back within {v1.window_days} days of delivery and we'll "
                    "give you a full refund.",
                ),
                at.pdf("returns-policy-v2", "§2 Return window", window_order),
            ],
        ),
        Difficulty(
            id="D9",
            title="Internal jargon",
            tests="Vocabulary mismatch between plain-language questions and jargon; semantic "
            "search.",
            expected_behaviour="Finds the jargon passages from a plain-language question.",
            locations=[
                loc
                for abbreviation in GLOSSARY
                for loc in (
                    at.slack_message(at.first_message_using(abbreviation), f"Uses {abbreviation}"),
                    at.first_macro_using(abbreviation),
                )
            ],
            glossary=dict(GLOSSARY),
        ),
        Difficulty(
            id="D10",
            title="Deliberate gaps",
            tests="Abstention.",
            expected_behaviour="Says the documents do not cover the topic and suggests "
            "escalating. Never invents a policy.",
            absent_topics=list(ABSENT_TOPICS),
            forbidden_terms=list(FORBIDDEN),
        ),
    ]
    return Manifest(
        corpus="data/corpus",
        policy_params="config/policy_params.yaml",
        seed=seed,
        as_of=ds.now.date().isoformat(),
        difficulties=difficulties,
    )


def manifest_yaml(manifest: Manifest) -> bytes:
    header = (
        "# Deliberate difficulties in the document corpus (docs/corpus-difficulties.md).\n"
        "# Generated by `make corpus`; do not edit by hand.\n"
    )
    body = yaml.safe_dump(
        manifest.model_dump(mode="json", exclude_none=True, exclude_defaults=False),
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    return (header + body).encode()


def load_manifest(content: bytes) -> Manifest:
    return Manifest.model_validate(yaml.safe_load(content))
