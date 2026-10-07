"""The #returns-exceptions channel, as a Slack workspace export.

Layout of the export (Slack's format): users.json, channels.json and one JSON file per
day under returns-exceptions/, each a list of messages. Thread parents carry
reply_count/replies, replies carry thread_ts and parent_user_id.

What the channel shows (see docs/corpus-difficulties.md):
- every H1 case (opened hygiene item accepted as defective) is posted here, because the
  H1 agent_note says "see #returns-exceptions". The team lead accepts an opened defective
  duvet "as an exception" (D4), and later agents cite it as a precedent;
- H2 threads take the opposite decision on the same kind of case;
- W1/W2 and C1-C5 threads show the other two undecided rules in practice;
- general messages use the team's jargon (D9) without ever expanding it.
Every decision message quotes the seeded agent_note verbatim.
"""

import json
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from lumora_corpus.params import day_month
from lumora_corpus.support.cases import SeedCase
from mock_api.seed.rand import rng

TEAM_ID = "T05LUMHOME"
CHANNEL_ID = "C05RTXCPT01"
CHANNEL_NAME = "returns-exceptions"
CHANNEL_CREATED = datetime(2025, 9, 15, 9, 12, tzinfo=UTC)
ANCHOR_TYPE = "Duvet"  # D4: the team lead accepts an opened defective duvet
H2_THREADS = 6
W_THREADS = 2  # per note id (W1, W2)


@dataclass(frozen=True, slots=True)
class SlackUser:
    id: str
    name: str
    real_name: str
    title: str


USERS: tuple[SlackUser, ...] = (
    SlackUser("U05LH1BDMR2", "burak.demir", "Burak Demir", "Support Team Lead"),
    SlackUser("U05LH2AOBY3", "aoife.byrne", "Aoife Byrne", "Support Agent"),
    SlackUser("U05LH3CWAL4", "ciaran.walsh", "Ciarán Walsh", "Support Agent"),
    SlackUser("U05LH4NKEL5", "niamh.kelly", "Niamh Kelly", "Support Agent"),
    SlackUser("U05LH5DMUR6", "darragh.murphy", "Darragh Murphy", "Support Agent"),
    SlackUser("U05LH6SDOY7", "sinead.doyle", "Sinéad Doyle", "Senior Support Agent"),
)
LEAD = USERS[0]
AGENTS = USERS[1:]

_FILLED = (
    "a seam split the first night",
    "the filling has bunched up on one side",
    "there's a hole along the hem",
    "the stitching came apart on first use",
)
_TEXTILE = (
    "the stitching came apart on first use",
    "the hem is unravelling",
    "the colour ran in the first wash",
    "there's a hole along the seam",
)
# What the customer says is wrong, by seeded hygiene product type.
DEFECTS: dict[str, tuple[str, ...]] = {
    "Duvet": _FILLED,
    "Pillow": _FILLED,
    "Weighted Blanket": ("the inner beads are leaking out", "a seam split the first night"),
    "Mattress": ("a spring is coming through the top", "it sags badly on one side"),
    "Mattress Topper": ("the foam has a deep dent after a week", "the cover zip is broken"),
    "Mattress Protector": ("the waterproof layer leaks", "the elastic skirt tore"),
    "Duvet Cover Set": ("the buttons came off", *_TEXTILE),
}
DEFAULT_DEFECTS = _TEXTILE

# H2 threads: someone points to the team lead's exception, the agent keeps the rejection.
H2_CHALLENGES = (
    "Didn't Burak take an opened one back as an exception on {anchor}?",
    "We accepted an opened {item} that was faulty on {anchor}, are we not doing that any more?",
    "Hm, I thought faulty ones were OK even if opened? See {anchor}.",
)
H2_ANSWERS = (
    "That was a one-off. The policy says opened hygiene items can't come back, so I'm "
    "sticking with it.",
    "Burak said that one wasn't a change to the policy. Opened is opened.",
    "The policy has no exception for faulty hygiene items, so I went with the policy.",
)

# Messages that are not about one case, posted on these dates (D9 jargon).
GENERAL: tuple[tuple[datetime, int, str], ...] = (
    (
        datetime(2025, 9, 15, 9, 20, tzinfo=UTC),
        0,
        f"Welcome to <#{CHANNEL_ID}|{CHANNEL_NAME}>. Post here when a return doesn't fit the "
        "usual rules: the RMA, the order number and what you decided, so we can see how we're "
        "handling these.",
    ),
    (
        datetime(2025, 10, 2, 10, 41, tzinfo=UTC),
        2,
        "NordPost RTS volume is up this week, mostly incomplete addresses. Please double-check "
        "the Eircode before you rebook.",
    ),
    (
        datetime(2025, 11, 6, 14, 5, tzinfo=UTC),
        4,
        "Third DOA kettle from the same batch this month. I've flagged it to the catalogue team.",
    ),
    (
        datetime(2025, 11, 24, 16, 30, tzinfo=UTC),
        5,
        "When a parcel comes back RTS, contact the customer before you refund. Most of them just "
        "want it sent again.",
    ),
    (
        datetime(2026, 1, 13, 11, 2, tzinfo=UTC),
        3,
        "Reminder: log an RMA for OOW requests too before you reject them, otherwise they don't "
        "show up in the weekly report.",
    ),
    (
        datetime(2026, 2, 3, 9, 47, tzinfo=UTC),
        1,
        "Finance asked us to put the amount in the ticket whenever we issue SC.",
    ),
    (
        datetime(2026, 2, 26, 15, 12, tzinfo=UTC),
        0,
        "Returns policy v2 is live for orders placed from {v2_from}. Please read it before you "
        "take on a return; the window and the refund rules have changed.",
    ),
    (
        datetime(2026, 4, 9, 13, 26, tzinfo=UTC),
        5,
        "If a customer reports a DOA appliance, ask for the model name from the rating plate "
        "first. It saves a round trip.",
    ),
    (
        datetime(2026, 5, 19, 10, 8, tzinfo=UTC),
        2,
        "Any RTS parcel that has been sitting in the warehouse for over a week: check the "
        "tracking history before you refund, some were delivered to a neighbour.",
    ),
    (
        datetime(2026, 6, 23, 12, 54, tzinfo=UTC),
        4,
        "OOW requests that come in through chat: ask for the order number first. Quite a few "
        "turn out to be fine.",
    ),
    (
        datetime(2026, 7, 30, 9, 15, tzinfo=UTC),
        3,
        "Hollis Freight collections are booked two working days out at the moment. Tell the "
        "customer when you raise the RMA.",
    ),
    (
        datetime(2026, 9, 1, 14, 40, tzinfo=UTC),
        1,
        "Has anyone had an SC refused by the customer? Not sure what to offer next.",
    ),
)


@dataclass(slots=True)
class Post:
    user: SlackUser
    at: datetime
    text: str
    reactions: list[tuple[str, SlackUser]] = field(default_factory=list)


@dataclass(slots=True)
class Thread:
    key: str  # what the thread is about, e.g. "H1:RMA-100151" or "general:3"
    posts: list[Post]


@dataclass(frozen=True, slots=True)
class SlackExport:
    files: dict[str, bytes]  # relative path -> content
    messages: list[dict[str, object]]  # every message, in ts order
    thread_keys: dict[str, str]  # ts of each message -> its thread key
    anchor: SeedCase  # the D4 case: the team lead's exception

    def lead_exception(self) -> dict[str, object]:
        """The team lead's message accepting the anchor case as an exception."""
        key = f"H1:{self.anchor.return_id}"
        return next(
            m
            for m in self.messages
            if self.thread_keys[str(m["ts"])] == key and m["user"] == LEAD.id
        )


def _other(r: random.Random, *exclude: SlackUser) -> SlackUser:
    return r.choice([a for a in AGENTS if a not in exclude])


def _timeline(case: SeedCase, r: random.Random, count: int) -> list[datetime]:
    """`count` moments between the request and the decision, in order."""
    span = min(case.decided_at - case.requested_at, timedelta(days=2))
    start = case.requested_at + span * r.uniform(0.05, 0.25)
    moments = [start]
    for _ in range(count - 1):
        moments.append(moments[-1] + timedelta(minutes=r.randint(6, 95)))
    if moments[-1] > case.decided_at:
        raise ValueError(f"Slack thread for {case.return_id} runs past its decision")
    return moments


def _thread(
    key: str, case: SeedCase, r: random.Random, lines: list[tuple[SlackUser, str]]
) -> Thread:
    times = _timeline(case, r, len(lines))
    return Thread(key, [Post(u, t, text) for (u, text), t in zip(lines, times, strict=True)])


def _anchor(cases: list[SeedCase]) -> SeedCase:
    duvets = [c for c in cases if c.product_type == ANCHOR_TYPE]
    return (duvets or cases)[0]


def _h1_threads(cases: list[SeedCase], anchor: SeedCase, seed: int) -> list[Thread]:
    threads: list[Thread] = []
    for case in cases:
        r = rng(seed, "slack-h1", case.return_id)
        agent = r.choice(AGENTS)
        defect = r.choice(DEFECTS.get(case.product_type, DEFAULT_DEFECTS))
        if case.customer_comment:
            # Quote the seeded comment rather than invent a different fault.
            defect = f'they say "{case.customer_comment.rstrip(".")}"'
        item = case.product_type.lower()
        ref = f"{case.return_id} ({case.order_id})"
        if case is anchor:
            lines = [
                (
                    agent,
                    f"<@{LEAD.id}> {ref}: the customer opened the {case.product_name} and it's "
                    f"DOA, {defect}. Opened bedding can't come back under the policy, but it's "
                    "faulty. Can we take it back?",
                ),
                (
                    LEAD,
                    f"Accept the {item} as an exception: it's defective, not just opened. Refund "
                    "as normal. This is a one-off, not a change to the policy.",
                ),
                (agent, f"Done, refund approved. Note on the RMA: {case.agent_note}"),
            ]
            thread = _thread(f"H1:{case.return_id}", case, r, lines)
            thread.posts[1].reactions.append(("white_check_mark", agent))
        elif case.requested_at < anchor.requested_at:
            lines = [
                (
                    agent,
                    f"<@{LEAD.id}> {ref}: opened {item}, but it's DOA, {defect}. OK to take it "
                    "back?",
                ),
                (LEAD, "Yes, it's faulty. Take it back as an exception and refund."),
                (agent, f"Thanks. Note on the RMA: {case.agent_note}"),
            ]
            thread = _thread(f"H1:{case.return_id}", case, r, lines)
        else:
            precedent = f"the {anchor.product_type.lower()} on {anchor.return_id}"
            lines = [
                (
                    agent,
                    f"{ref}: opened {case.product_name}, DOA, {defect}. Same as {precedent}, "
                    "so I'm accepting it as an exception.",
                ),
                (agent, f"Note on the RMA: {case.agent_note}"),
            ]
            thread = _thread(f"H1:{case.return_id}", case, r, lines)
        threads.append(thread)
    return threads


def _spread(cases: list[SeedCase], count: int) -> list[SeedCase]:
    """`count` cases evenly spaced through the list."""
    if len(cases) <= count:
        return cases
    return [cases[round(i * (len(cases) - 1) / (count - 1))] for i in range(count)]


def _h2_threads(cases: list[SeedCase], anchor: SeedCase, seed: int) -> list[Thread]:
    later = [c for c in cases if c.requested_at > anchor.requested_at]
    threads: list[Thread] = []
    for case in _spread(later, H2_THREADS):
        r = rng(seed, "slack-h2", case.return_id)
        agent = r.choice(AGENTS)
        other = _other(r, agent)
        lines = [
            (
                agent,
                f"{case.return_id} ({case.order_id}): the customer opened the "
                f"{case.product_name} and says it's faulty. Rejected under the opened-packaging "
                f"rule. Note: {case.agent_note}",
            ),
            (
                other,
                r.choice(H2_CHALLENGES).format(
                    anchor=anchor.return_id, item=anchor.product_type.lower()
                ),
            ),
            (agent, r.choice(H2_ANSWERS)),
        ]
        threads.append(_thread(f"H2:{case.return_id}", case, r, lines))
    return threads


def _window_threads(cases: dict[str, list[SeedCase]], seed: int) -> list[Thread]:
    threads: list[Thread] = []
    w1 = _spread(cases.get("W1", []), W_THREADS)
    w2 = _spread(cases.get("W2", []), W_THREADS)
    for case in sorted(w1 + w2, key=lambda c: c.requested_at):
        r = rng(seed, "slack-window", case.return_id)
        agent = r.choice(AGENTS)
        other = _other(r, agent)
        ref = f"{case.return_id} ({case.order_id})"
        if case.note_id == "W1":
            lines = [
                (
                    agent,
                    f"{ref}: change of mind, requested {case.days_since_order} days after the "
                    f"order but only {case.days_since_delivery} days after delivery. OOW if we "
                    "count from the order date, fine if we count from delivery. Which one?",
                ),
                (
                    other,
                    f"I count from delivery, they've only had it {case.days_since_delivery} "
                    f"days. Approved it, note: {case.agent_note}",
                ),
            ]
        else:
            lines = [
                (
                    agent,
                    f"{ref}: change of mind, {case.days_since_order} days after the order, so "
                    f"I'm rejecting it under v2. Note: {case.agent_note}",
                ),
                (
                    other,
                    "The customer says it arrived late. Is it OOW either way, or is anyone "
                    "counting from delivery on these?",
                ),
            ]
        if not threads:
            lines.append(
                (
                    LEAD,
                    "Keep handling these the way you have been for now. I've asked Selin to "
                    "confirm which date the window counts from.",
                )
            )
        threads.append(_thread(f"{case.note_id}:{case.return_id}", case, r, lines))
    return threads


def _campaign_threads(cases: dict[str, list[SeedCase]], seed: int) -> list[Thread]:
    threads: list[Thread] = []
    for note_id in ("C1", "C2", "C3", "C4", "C5"):
        group = [c for c in cases.get(note_id, []) if c.requested_at > CHANNEL_CREATED]
        if not group:
            continue
        case = group[len(group) // 2]
        r = rng(seed, "slack-campaign", case.return_id)
        agent = r.choice(AGENTS)
        other = _other(r, agent)
        ref = f"{case.return_id} ({case.order_id})"
        note = case.agent_note
        name = case.product_name
        match note_id:
            case "C1":
                lines = [
                    (
                        agent,
                        f"{ref}: change of mind on the {name}, it's an outlet item. Is "
                        "outlet a campaign item?",
                    ),
                    (
                        other,
                        f"The policy doesn't say. I've been doing exchanges for outlet, so "
                        f"I offered an exchange. Note: {note}",
                    ),
                ]
            case "C2":
                lines = [
                    (
                        agent,
                        f"{ref}: outlet {name}, change of mind. I can't find anything in "
                        f"the policy that stops a refund, so I refunded it. Note: {note}",
                    ),
                    (other, "I've been giving exchanges on outlet items :shrug:"),
                ]
            case "C3":
                lines = [
                    (
                        agent,
                        f"{ref}: the order used {case.coupon_code}. Treating it as a "
                        f"campaign item, exchange only. Note: {note}",
                    ),
                    (other, "Is a coupon order a campaign item though?"),
                ]
            case "C4":
                lines = [
                    (
                        agent,
                        f"{ref}: {case.coupon_code} on the order, change of mind. Refunded "
                        f"it, a coupon doesn't make it a campaign item. Note: {note}",
                    ),
                    (other, "I did the opposite on one last week."),
                ]
            case _:
                lines = [
                    (
                        agent,
                        f"{ref}: campaign item, changed mind, so I rejected the return. "
                        f"Note: {note}",
                    ),
                    (other, "Did they take the SC?"),
                    (agent, "Yes, SC issued."),
                ]
        threads.append(_thread(f"{note_id}:{case.return_id}", case, r, lines))
    return threads


def _general_threads(policy_change: date) -> list[Thread]:
    return [
        Thread(
            f"general:{i}", [Post(USERS[user], at, text.format(v2_from=day_month(policy_change)))]
        )
        for i, (at, user, text) in enumerate(GENERAL)
    ]


def _ts(at: datetime, used: set[str]) -> str:
    seconds = int(at.timestamp())
    n = 100
    while f"{seconds}.{n:06d}" in used:
        n += 100
    ts = f"{seconds}.{n:06d}"
    used.add(ts)
    return ts


def _profile(user: SlackUser) -> dict[str, object]:
    return {
        "avatar_hash": f"g{user.id[-10:].lower()}",
        "first_name": user.real_name.split(" ", 1)[0],
        "real_name": user.real_name,
        "display_name": user.real_name,
        "team": TEAM_ID,
        "name": user.name,
        "is_restricted": False,
        "is_ultra_restricted": False,
    }


def build_slack(cases: dict[str, list[SeedCase]], seed: int, policy_change: date) -> SlackExport:
    h1 = cases.get("H1", [])
    if not h1:
        raise ValueError("The seed has no H1 cases; the Slack export needs them.")
    anchor = _anchor(h1)
    created = min(CHANNEL_CREATED, h1[0].requested_at - timedelta(days=7))
    threads = (
        _general_threads(policy_change)
        + _h1_threads(h1, anchor, seed)
        + _h2_threads(cases.get("H2", []), anchor, seed)
        + _window_threads(cases, seed)
        + _campaign_threads(cases, seed)
    )

    used: set[str] = set()
    r = rng(seed, "slack-ids")
    keyed: list[tuple[datetime, str, int, Post]] = [
        (post.at, thread.key, i, post) for thread in threads for i, post in enumerate(thread.posts)
    ]
    keyed.sort(key=lambda k: (k[0], k[1], k[2]))
    ts_of: dict[tuple[str, int], str] = {}
    for at, key, i, _ in keyed:
        ts_of[(key, i)] = _ts(at, used)

    messages: list[dict[str, object]] = []
    thread_keys: dict[str, str] = {}
    by_key = {t.key: t for t in threads}
    for _, key, i, post in keyed:
        ts = ts_of[(key, i)]
        thread = by_key[key]
        message: dict[str, object] = {
            "client_msg_id": str(uuid.UUID(int=r.getrandbits(128), version=4)),
            "type": "message",
            "text": post.text,
            "user": post.user.id,
            "ts": ts,
            "team": TEAM_ID,
            "user_team": TEAM_ID,
            "source_team": TEAM_ID,
            "user_profile": _profile(post.user),
        }
        parent_ts = ts_of[(key, 0)]
        if len(thread.posts) > 1:
            message["thread_ts"] = parent_ts
            if i == 0:
                replies = [(p.user.id, ts_of[(key, j)]) for j, p in enumerate(thread.posts)][1:]
                message["reply_count"] = len(replies)
                message["reply_users_count"] = len({u for u, _ in replies})
                message["latest_reply"] = replies[-1][1]
                message["reply_users"] = sorted({u for u, _ in replies})
                message["replies"] = [{"user": u, "ts": t} for u, t in replies]
                message["is_locked"] = False
                message["subscribed"] = False
            else:
                message["parent_user_id"] = thread.posts[0].user.id
        if post.reactions:
            grouped: defaultdict[str, list[str]] = defaultdict(list)
            for name, user in post.reactions:
                grouped[name].append(user.id)
            message["reactions"] = [
                {"name": name, "users": users, "count": len(users)}
                for name, users in grouped.items()
            ]
        messages.append(message)
        thread_keys[ts] = key

    days: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for message in messages:
        day = datetime.fromtimestamp(float(str(message["ts"])), UTC).date().isoformat()
        days[day].append(message)

    files: dict[str, bytes] = {
        "users.json": _json([_user(u) for u in USERS]),
        "channels.json": _json([_channel(created)]),
    }
    for day, day_messages in days.items():
        files[f"{CHANNEL_NAME}/{day}.json"] = _json(day_messages)
    return SlackExport(files=files, messages=messages, thread_keys=thread_keys, anchor=anchor)


def _user(user: SlackUser) -> dict[str, object]:
    first, last = user.real_name.split(" ", 1)
    return {
        "id": user.id,
        "team_id": TEAM_ID,
        "name": user.name,
        "deleted": False,
        "real_name": user.real_name,
        "tz": "Europe/Dublin",
        "tz_label": "Irish Standard Time",
        "is_admin": user is LEAD,
        "is_owner": False,
        "is_bot": False,
        "is_app_user": False,
        "profile": {
            "title": user.title,
            "real_name": user.real_name,
            "display_name": user.real_name,
            "first_name": first,
            "last_name": last,
            "team": TEAM_ID,
        },
    }


def _channel(created: datetime) -> dict[str, object]:
    stamp = int(created.timestamp())
    return {
        "id": CHANNEL_ID,
        "name": CHANNEL_NAME,
        "created": stamp,
        "creator": LEAD.id,
        "is_archived": False,
        "is_general": False,
        "members": [u.id for u in USERS],
        "topic": {"value": "", "creator": "", "last_set": 0},
        "purpose": {
            "value": "Returns that don't fit the usual rules. Post the RMA, the order and what "
            "you decided.",
            "creator": LEAD.id,
            "last_set": stamp,
        },
        "pins": [],
    }


def _json(value: object) -> bytes:
    return (json.dumps(value, indent=4, ensure_ascii=False) + "\n").encode()
