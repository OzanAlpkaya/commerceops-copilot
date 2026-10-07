"""The committed manifest points at text that really is in the committed corpus."""

import json
from functools import cache
from pathlib import Path

import pytest

from lumora_corpus.layout import Layout
from lumora_corpus.manifest import Location, Manifest, build_manifest, load_manifest, table_cells
from lumora_corpus.policies.build import RenderedDoc
from lumora_corpus.render.pdf_text import normalise, page_texts
from lumora_corpus.support.build import build_support
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset

CORPUS = Path(__file__).parents[2] / "data" / "corpus"


@pytest.fixture(scope="module")
def manifest(repo_layout: Layout) -> Manifest:
    return load_manifest(repo_layout.manifest.read_bytes())


@cache
def _pages(document: str) -> list[str]:
    return page_texts((CORPUS / document).read_bytes())


def _check(location: Location, sources: Path) -> None:
    match location.kind:
        case "text" | "table_row":
            assert location.page is not None
            stem = Path(location.document).stem
            assert location.text in (sources / f"{stem}.md").read_text()
            page = normalise(_pages(location.document)[location.page - 1])
            needles = (
                table_cells(location.text) if location.kind == "table_row" else [location.text]
            )
            for needle in needles:
                assert normalise(needle) in page, (location.document, location.page, needle)
        case "slack_message":
            messages = json.loads((CORPUS / location.document).read_text())
            message = next(m for m in messages if m["ts"] == location.ts)
            assert message["text"] == location.text
        case "zendesk_macro":
            macros = json.loads((CORPUS / location.document).read_text())["macros"]
            macro = next(m for m in macros if m["id"] == location.macro_id)
            assert macro["title"] == location.section
            assert location.text in json.dumps(macro, ensure_ascii=False)


def test_every_difficulty_is_listed_once(manifest: Manifest) -> None:
    assert [d.id for d in manifest.difficulties] == [f"D{i}" for i in range(1, 11)]
    rules = {d.id: d.undecided_rule for d in manifest.difficulties if d.undecided_rule}
    assert rules == {"D2": 1, "D3": 2, "D4": 3}


def test_every_location_is_in_the_corpus(manifest: Manifest, repo_layout: Layout) -> None:
    for difficulty in manifest.difficulties:
        for location in difficulty.locations:
            _check(location, repo_layout.policy_sources)
        if difficulty.id != "D10":
            assert difficulty.locations, difficulty.id


def test_d4_points_at_policy_warranty_and_slack(manifest: Manifest) -> None:
    d4 = next(d for d in manifest.difficulties if d.id == "D4")
    kinds = {(loc.document.split("/")[0], loc.kind) for loc in d4.locations}
    assert ("policies", "text") in kinds and ("slack", "slack_message") in kinds
    assert any("as an exception" in loc.text for loc in d4.locations)


def test_d9_lists_each_abbreviation_in_slack_and_zendesk(manifest: Manifest) -> None:
    d9 = next(d for d in manifest.difficulties if d.id == "D9")
    assert d9.glossary is not None
    for abbreviation in d9.glossary:
        sources = {loc.kind for loc in d9.locations if abbreviation in loc.text}
        assert {"slack_message", "zendesk_macro"} <= sources, abbreviation


def test_manifest_builds_on_the_fixture(
    fixture_seed: tuple[SeedDataset, SeedConfig], policy_docs: dict[str, RenderedDoc]
) -> None:
    """The builder's own checks (text on the stated page or message) pass end to end."""
    ds, cfg = fixture_seed
    support = build_support(ds, cfg.seed, cfg.policy)
    docs = list(policy_docs.values())
    manifest = build_manifest(docs, support, ds, cfg.policy, cfg.seed)
    assert len(manifest.difficulties) == 10
