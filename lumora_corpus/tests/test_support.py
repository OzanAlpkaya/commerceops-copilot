"""Slack export and Zendesk macros, built from the synthetic fixture dataset."""

import json
from datetime import UTC, datetime

import pytest

from lumora_corpus.support.build import SupportCorpus, build_support
from lumora_corpus.support.slack import CHANNEL_NAME, LEAD, USERS
from lumora_corpus.support.zendesk import CHANGED_MIND
from lumora_corpus.terms import GLOSSARY, expands, forbidden_in, uses
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset
from mock_api.seed.returns import NOTE_TEMPLATES


def _day_files(support: SupportCorpus) -> dict[str, list[dict[str, object]]]:
    return {
        path: json.loads(content)
        for path, content in support.slack.files.items()
        if path.startswith(f"{CHANNEL_NAME}/")
    }


def _macros(support: SupportCorpus) -> list[dict[str, object]]:
    return json.loads(support.zendesk["macros.json"])["macros"]


def _macro_text(macro: dict[str, object]) -> str:
    actions = macro["actions"]
    assert isinstance(actions, list)
    body = next(a["value"] for a in actions if a["field"] == "comment_value_html")
    return f"{macro['title']}\n{macro['description']}\n{body}"


def test_build_is_deterministic(
    fixture_seed: tuple[SeedDataset, SeedConfig], fixture_support: SupportCorpus
) -> None:
    ds, cfg = fixture_seed
    again = build_support(ds, cfg.seed, cfg.policy)
    assert again.slack.files == fixture_support.slack.files
    assert again.zendesk == fixture_support.zendesk


def test_slack_export_format(fixture_support: SupportCorpus) -> None:
    files = fixture_support.slack.files
    users = json.loads(files["users.json"])
    channels = json.loads(files["channels.json"])
    assert [u["id"] for u in users] == [u.id for u in USERS]
    assert [c["name"] for c in channels] == [CHANNEL_NAME]

    seen: list[str] = []
    by_ts: dict[str, dict[str, object]] = {}
    for path, messages in sorted(_day_files(fixture_support).items()):
        day = path.removeprefix(f"{CHANNEL_NAME}/").removesuffix(".json")
        for message in messages:
            ts = str(message["ts"])
            assert datetime.fromtimestamp(float(ts), UTC).date().isoformat() == day
            assert message["type"] == "message" and message["user"] in {u.id for u in USERS}
            seen.append(ts)
            by_ts[ts] = message
    assert seen == sorted(seen, key=float) and len(seen) == len(set(seen))
    assert all(float(ts) >= channels[0]["created"] for ts in seen)

    for message in by_ts.values():
        if "replies" in message:
            replies = message["replies"]
            assert isinstance(replies, list)
            assert message["reply_count"] == len(replies)
            for reply in replies:
                child = by_ts[reply["ts"]]
                assert child["thread_ts"] == message["ts"] == message["thread_ts"]
                assert child["parent_user_id"] == message["user"]


def test_every_h1_case_is_in_the_channel_with_its_note(
    fixture_support: SupportCorpus,
) -> None:
    slack = fixture_support.slack
    keys = set(slack.thread_keys.values())
    for case in fixture_support.cases["H1"]:
        assert f"H1:{case.return_id}" in keys
        key = f"H1:{case.return_id}"
        thread = [m for m in slack.messages if slack.thread_keys[str(m["ts"])] == key]
        assert any(case.agent_note in str(m["text"]) for m in thread)
        assert case.return_id in str(thread[0]["text"])


def test_case_threads_quote_notes_and_fit_the_timeline(fixture_support: SupportCorpus) -> None:
    slack = fixture_support.slack
    cases = {c.return_id: c for group in fixture_support.cases.values() for c in group}
    threads: dict[str, list[dict[str, object]]] = {}
    for message in slack.messages:
        threads.setdefault(slack.thread_keys[str(message["ts"])], []).append(message)
    for key, messages in threads.items():
        if key.startswith("general:"):
            continue
        note_id, return_id = key.split(":")
        case = cases[return_id]
        assert case.note_id == note_id
        assert any(case.agent_note in str(m["text"]) for m in messages), key
        assert case.order_id in str(messages[0]["text"])
        for message in messages:
            at = datetime.fromtimestamp(float(str(message["ts"])), UTC)
            assert case.requested_at <= at <= case.decided_at, key


def test_d4_team_lead_exception(fixture_support: SupportCorpus) -> None:
    lead = fixture_support.slack.lead_exception()
    anchor = fixture_support.slack.anchor
    assert lead["user"] == LEAD.id
    assert "as an exception" in str(lead["text"])
    assert anchor.note_id == "H1"
    h2 = [k for k in fixture_support.slack.thread_keys.values() if k.startswith("H2:")]
    assert h2, "the opposite decision must be in the channel"


def test_d8_changed_mind_macro_is_outdated(fixture_support: SupportCorpus) -> None:
    macro = next(m for m in _macros(fixture_support) if m["title"] == CHANGED_MIND)
    text = _macro_text(macro)
    assert "within 30 days of delivery" in text and "full refund" in text
    assert str(macro["updated_at"]) < "2026-03-01"


def test_zendesk_export_format(fixture_support: SupportCorpus) -> None:
    export = json.loads(fixture_support.zendesk["macros.json"])
    macros = export["macros"]
    assert export["count"] == len(macros) == 25
    assert len({m["id"] for m in macros}) == len(macros)
    assert len({m["title"] for m in macros}) == len(macros)
    for macro in macros:
        assert macro["created_at"] <= macro["updated_at"]
        fields = [a["field"] for a in macro["actions"]]
        assert fields[:2] == ["comment_value_html", "comment_mode_is_public"]


def test_internal_macros_use_the_seeded_note_wording(fixture_support: SupportCorpus) -> None:
    internal = [m for m in _macros(fixture_support) if str(m["title"]).startswith("Internal")]
    bodies = {_macro_text(m).split("\n")[-1] for m in internal}
    assert bodies == {f"<p>{NOTE_TEMPLATES[n]}</p>" for n in ("H2", "C1", "C2", "C5")}


def _texts(support: SupportCorpus) -> list[str]:
    return [str(m["text"]) for m in support.slack.messages] + [
        _macro_text(m) for m in _macros(support)
    ]


@pytest.mark.parametrize("abbreviation", sorted(GLOSSARY))
def test_d9_jargon_is_never_expanded(abbreviation: str, fixture_support: SupportCorpus) -> None:
    texts = _texts(fixture_support)
    assert any(uses(abbreviation, t) for t in texts), abbreviation
    for text in texts:
        if uses(abbreviation, text):
            assert not expands(abbreviation, text), text


def test_d9_check_catches_an_expansion() -> None:
    assert expands("SC", "Offered SC (store credit) instead")
    assert not uses("SC", "SCAN") and uses("SC", "Did they take the SC?")


def test_d10_forbidden_terms_are_absent(fixture_support: SupportCorpus) -> None:
    for text in _texts(fixture_support):
        assert forbidden_in(text) == [], text
