"""Fill the policy templates, keep the Markdown as ground truth, and render the PDFs."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

from lumora_corpus import params
from lumora_corpus.layout import Layout, replace_dir
from lumora_corpus.render.markdown_pdf import PdfMeta, render_pdf
from lumora_corpus.render.pdf_text import page_texts
from mock_api.enums import ReturnReason
from mock_api.policy import PolicyParams
from mock_api.seed.campaigns import SEASONAL, WELCOME


@dataclass(frozen=True, slots=True)
class PolicyDoc:
    name: str  # file stem, e.g. "returns-policy-v2"
    template: str
    title: str
    published: date
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RenderedDoc:
    name: str
    title: str
    markdown: str
    pdf: bytes
    pages: list[str]  # text layer per page

    @property
    def pdf_name(self) -> str:
        return f"{self.name}.pdf"


@dataclass(frozen=True, slots=True)
class CampaignRun:
    label: str
    code: str
    percent: int
    start: date
    end: date

    @property
    def dates(self) -> str:
        return params.date_range(self.start, self.end)


DOCS: tuple[PolicyDoc, ...] = (
    PolicyDoc(
        "returns-policy-v1",
        "returns-policy.md.j2",
        "Returns Policy",
        params.V1_PUBLISHED,
        {"version": "v1"},
    ),
    PolicyDoc(
        "returns-policy-v2",
        "returns-policy.md.j2",
        "Returns Policy",
        params.V2_PUBLISHED,
        {"version": "v2"},
    ),
    PolicyDoc(
        "warranty-and-defects",
        "warranty-and-defects.md.j2",
        "Warranty and Defects Policy",
        params.SUPPORT_DOCS_PUBLISHED,
    ),
    PolicyDoc(
        "shipping-and-delivery",
        "shipping-and-delivery.md.j2",
        "Shipping & Delivery Policy",
        params.SUPPORT_DOCS_PUBLISHED,
    ),
    PolicyDoc(
        "promo-codes-2026",
        "promo-codes-2026.md.j2",
        f"Promotions and Campaign Codes {params.PROMO_YEAR}",
        params.PROMO_PUBLISHED,
    ),
)


def campaign_runs(year: int) -> tuple[list[CampaignRun], list[CampaignRun]]:
    """(runs live during `year`, earlier runs back to two years before), by start date."""
    runs = [
        CampaignRun(c.label, c.code, c.percent, *c.dates(y))
        for y in range(year - 2, year + 1)
        for c in SEASONAL
    ]
    runs.sort(key=lambda r: r.start)
    current = [r for r in runs if year in (r.start.year, r.end.year)]
    previous = [r for r in runs if r not in current]
    return current, previous


def _environment() -> Environment:
    env = Environment(
        loader=PackageLoader("lumora_corpus", "policies/templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters["long_date"] = params.long_date
    env.filters["eur"] = params.eur
    env.filters["in_words"] = params.in_words
    return env


def render_markdown(doc: PolicyDoc, policy: PolicyParams) -> str:
    current, previous = campaign_runs(params.PROMO_YEAR)
    version = doc.context.get("version", "v2")
    context: dict[str, Any] = {
        "p": policy,
        "v": getattr(policy.versions, version),
        "v1": policy.versions.v1,
        "v2": policy.versions.v2,
        "fee": policy.return_fees_eur[ReturnReason.CHANGED_MIND],
        "published": doc.published,
        "contact_email": params.CONTACT_EMAIL,
        "chat_hours": params.CHAT_HOURS,
        "year": params.PROMO_YEAR,
        "current": current,
        "previous": previous,
        "welcome": WELCOME,
        **doc.context,
    }
    return _environment().get_template(doc.template).render(context)


def write_policies(docs: list[RenderedDoc], layout: Layout) -> None:
    replace_dir(layout.policies, {d.pdf_name: d.pdf for d in docs})
    replace_dir(layout.policy_sources, {f"{d.name}.md": d.markdown.encode() for d in docs})


def build_policies(policy: PolicyParams) -> list[RenderedDoc]:
    rendered: list[RenderedDoc] = []
    for doc in DOCS:
        markdown = render_markdown(doc, policy)
        pdf = render_pdf(markdown, PdfMeta(title=doc.title, footer=f"Lumora Home · {doc.title}"))
        rendered.append(RenderedDoc(doc.name, doc.title, markdown, pdf, page_texts(pdf)))
    return rendered
