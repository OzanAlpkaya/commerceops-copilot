"""Zendesk macros, as returned by GET /api/v2/macros.json.

About 25 macros the support team uses. Two things are deliberate:
- "Return – changed mind" was written for policy v1 and never updated (D8): it promises a
  full refund within 30 days of delivery;
- internal-note macros reuse the seeded agent_note wording (H2, C1, C2, C5), including
  two that contradict each other on outlet items, and their descriptions cite the first
  seeded return that used them.
The team's jargon (D9) appears in titles and notes and is never expanded.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from lumora_corpus.support.cases import SeedCase
from mock_api.policy import PolicyParams
from mock_api.seed.returns import NOTE_TEMPLATES

URL = "https://lumorahome.zendesk.com/api/v2/macros/{id}.json"
FIRST_ID = 26013470001
CHANGED_MIND = "Return – changed mind"


@dataclass(frozen=True, slots=True)
class Macro:
    title: str
    description: str
    paragraphs: tuple[str, ...]  # the comment, one HTML paragraph each
    public: bool
    status: str  # ticket status the macro sets
    tags: str
    created: datetime
    updated: datetime


def _when(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 9, 30, tzinfo=UTC)


GREETING = "Hi {{ticket.requester.first_name}},"
SIGN_OFF = "Kind regards,<br>{{current_user.first_name}}, Lumora Home Customer Care"


def _hello(*body: str) -> tuple[str, ...]:
    return (GREETING, *body, SIGN_OFF)


def _internal(
    cases: dict[str, list[SeedCase]],
    note_id: str,
    title: str,
    description: str,
    status: str,
    tags: str,
) -> Macro:
    """An internal-note macro with a seeded agent_note, created for its first seeded case."""
    group = cases.get(note_id, [])
    created = _when(2025, 1, 6)
    if group:
        first = group[0]
        description += f" First used on {first.return_id}."
        day = first.decided_at.date()
        created = _when(day.year, day.month, day.day)
    return Macro(
        title, description, (NOTE_TEMPLATES[note_id],), False, status, tags, created, created
    )


def macros(cases: dict[str, list[SeedCase]], policy: PolicyParams) -> list[Macro]:
    claims = policy.claims
    refund_days = policy.refund_working_days
    v1_window = policy.versions.v1.window_days
    collection = policy.collection
    return [
        Macro(
            CHANGED_MIND,
            "Customer changed their mind and wants to send an item back.",
            _hello(
                "Thanks for getting in touch about your order.",
                f"You can send it back within {v1_window} days of delivery and we'll give you a "
                "full refund. Returning an item costs you nothing.",
                "We've raised an RMA for you and will email the returns label shortly. Pack the "
                "item securely, attach the label and drop it at any post office.",
            ),
            True,
            "pending",
            "returns changed_mind",
            _when(2024, 6, 3),
            _when(2024, 6, 3),
        ),
        Macro(
            "Return – defective item",
            "Item has a fault. Ask for photos if the customer has not sent any.",
            _hello(
                "I'm sorry the item isn't working as it should.",
                "Could you send us a few photos or a short video that show the fault? Once we "
                "have them we'll arrange a free return and send a replacement or refund you, "
                "whichever you prefer.",
            ),
            True,
            "pending",
            "returns defective",
            _when(2024, 6, 3),
            _when(2026, 2, 20),
        ),
        Macro(
            "Return – wrong item",
            "We sent a different item from the one ordered.",
            _hello(
                "I'm sorry we sent you the wrong item.",
                "We'll collect it free of charge and send the right one, or refund you if you "
                "prefer. Please keep the item in its packaging until it is collected.",
            ),
            True,
            "pending",
            "returns wrong_item",
            _when(2024, 6, 3),
            _when(2025, 4, 11),
        ),
        Macro(
            "Return – damaged in transit",
            "Item arrived damaged. Photos needed within the reporting period.",
            _hello(
                "I'm sorry your order arrived damaged.",
                f"Please send us photos of the item and the packaging. Damage needs to be "
                f"reported within {claims.damaged_report_days} days of delivery. Keep the "
                "packaging until we've sorted this out, as the carrier may want to see it.",
            ),
            True,
            "pending",
            "returns damaged_in_transit",
            _when(2024, 6, 3),
            _when(2026, 2, 20),
        ),
        Macro(
            "Return – hygiene item opened",
            "Customer wants to return an opened pillow, bedding, mattress or similar item.",
            _hello(
                "Thanks for your message.",
                "For hygiene reasons we can't accept returns of opened pillows, bedding, "
                "mattresses, mattress protectors, towels, bathrobes, mattress toppers or "
                "weighted blankets. Unopened items in their sealed packaging can be returned as "
                "normal.",
            ),
            True,
            "solved",
            "returns hygiene",
            _when(2024, 6, 3),
            _when(2026, 2, 20),
        ),
        _internal(
            cases,
            "H2",
            "Internal – hygiene item opened, reject",
            "Internal note for opened hygiene items.",
            "solved",
            "returns hygiene rejected",
        ),
        _internal(
            cases,
            "C1",
            "Internal – outlet item, exchange",
            "Internal note: outlet item, change of mind, exchange offered.",
            "pending",
            "returns outlet exchange",
        ),
        _internal(
            cases,
            "C2",
            "Internal – outlet item, refund",
            "Internal note: outlet item, change of mind, refunded.",
            "pending",
            "returns outlet refund",
        ),
        _internal(
            cases,
            "C5",
            "Internal – campaign item, changed mind",
            "Internal note: campaign item, change of mind, return rejected.",
            "solved",
            "returns campaign rejected",
        ),
        Macro(
            "Return – large item collection",
            f"Item over {collection.threshold_kg} kg: book a collection.",
            _hello(
                f"Large items are collected by {collection.carrier}. They'll contact you to "
                "book a collection date. Please have the item ready at ground-floor level and, "
                "if you still have it, in its original packaging.",
            ),
            True,
            "pending",
            "returns collection hollis",
            _when(2024, 6, 3),
            _when(2026, 2, 20),
        ),
        Macro(
            "OOW – decline change of mind",
            "Change-of-mind request that came in too late.",
            _hello(
                "Thanks for getting in touch.",
                "I'm sorry, but it's too late to return this item for a change of mind under "
                "our Returns Policy, so we can't accept the return. If the item is "
                "faulty, let us know and we'll look at it under our Warranty and Defects Policy.",
            ),
            True,
            "solved",
            "returns oow",
            _when(2024, 9, 9),
            _when(2025, 1, 15),
        ),
        Macro(
            "Refund – issued",
            "Refund processed after the return was received.",
            _hello(
                "Your returned item has reached our warehouse and we've processed your refund "
                "to the original payment method.",
                "Your bank or card provider may take a few days to show it.",
            ),
            True,
            "solved",
            "refund issued",
            _when(2024, 6, 3),
            _when(2024, 6, 3),
        ),
        Macro(
            "Refund – when will I get it",
            "Customer asks when their refund will arrive.",
            _hello(
                f"We process refunds within {refund_days} working days of receiving the "
                "returned item. Once it's processed, your bank or card provider may take a few "
                "more days to show the money.",
            ),
            True,
            "solved",
            "refund timing",
            _when(2024, 6, 3),
            _when(2026, 2, 20),
        ),
        Macro(
            "Exchange – confirm",
            "Confirm an exchange for a different size or colour.",
            _hello(
                "We've set up your exchange. As soon as the returned item reaches us, we'll "
                "send the replacement at no extra delivery charge.",
            ),
            True,
            "pending",
            "exchange",
            _when(2024, 6, 3),
            _when(2026, 2, 20),
        ),
        Macro(
            "SC – issue",
            "Internal note when SC is issued instead of a refund.",
            ("SC issued. Amount and reason added to the ticket for finance.",),
            False,
            "solved",
            "sc",
            _when(2025, 2, 3),
            _when(2026, 2, 3),
        ),
        Macro(
            "RTS – contact customer",
            "Parcel came back to the warehouse undelivered.",
            _hello(
                "Your parcel has come back to our warehouse because the carrier couldn't "
                "deliver it. Could you confirm your full address and Eircode? We'll send it out "
                "again as soon as we hear from you.",
            ),
            True,
            "pending",
            "delivery rts",
            _when(2024, 10, 1),
            _when(2025, 10, 2),
        ),
        Macro(
            "DOA – appliance",
            "Appliance does not work out of the box.",
            _hello(
                "I'm sorry the appliance isn't working. Please stop using it and unplug it.",
                "Could you send us the model name from the rating plate and a short video "
                "showing what happens when you switch it on? We'll then arrange a free return "
                "and a replacement or refund.",
            ),
            True,
            "pending",
            "returns defective doa appliance",
            _when(2024, 11, 18),
            _when(2026, 4, 9),
        ),
        Macro(
            "Delivery – where is my order",
            "Customer asks about an order that has not arrived yet.",
            _hello(
                "Your order is on its way. You can follow it with the tracking number in your "
                "dispatch email on the carrier's website.",
                "The estimated delivery date on your order confirmation is the one to rely on. "
                "If the order hasn't arrived by then, reply to this email and we'll check with "
                "the carrier.",
            ),
            True,
            "solved",
            "delivery wismo",
            _when(2024, 6, 3),
            _when(2026, 2, 20),
        ),
        Macro(
            "Delivery – late",
            "Order is past its estimated delivery date.",
            _hello(
                "I'm sorry your order is late. I've asked the carrier to check where it is and "
                "will update you as soon as I hear back.",
            ),
            True,
            "pending",
            "delivery late",
            _when(2024, 6, 3),
            _when(2024, 6, 3),
        ),
        Macro(
            "Delivery – parcel not found",
            "The carrier cannot find the parcel.",
            _hello(
                "The carrier has confirmed that they can't find your parcel. I'm sorry about "
                "this. We can send a replacement or refund you, whichever you prefer.",
            ),
            True,
            "pending",
            "delivery lost",
            _when(2024, 6, 3),
            _when(2025, 7, 7),
        ),
        Macro(
            "Order – cancel before dispatch",
            "Cancel an order that has not left the warehouse.",
            _hello(
                f"We've cancelled your order. As it hadn't left our warehouse, you'll get the "
                f"full amount back to your original payment method within {refund_days} "
                "working days.",
            ),
            True,
            "solved",
            "order cancel",
            _when(2024, 6, 3),
            _when(2026, 2, 20),
        ),
        Macro(
            "Order – change delivery address",
            "Customer wants to change the delivery address.",
            _hello(
                "We can change the delivery address until the order is handed to the carrier. "
                "Please reply with the new address and Eircode.",
            ),
            True,
            "pending",
            "order address",
            _when(2024, 6, 3),
            _when(2024, 6, 3),
        ),
        Macro(
            "Escalate – team lead",
            "The policy does not clearly cover the case.",
            (
                "Escalated to the team lead: the policy doesn't clearly cover this case. Please "
                "don't promise the customer an outcome until it has been decided.",
            ),
            False,
            "open",
            "escalated team_lead",
            _when(2025, 10, 20),
            _when(2025, 10, 20),
        ),
        Macro(
            "Request – photos",
            "Ask the customer for photos.",
            _hello(
                "Could you send us a few photos of the item, and of the packaging if you still "
                "have it? You can reply to this email and attach them.",
            ),
            True,
            "pending",
            "photos",
            _when(2024, 6, 3),
            _when(2024, 6, 3),
        ),
        Macro(
            "Close – no response",
            "Close a ticket after no reply from the customer.",
            _hello(
                "We haven't heard back from you, so we're closing this request for now. Just "
                "reply to this email if you still need help and the ticket will reopen.",
            ),
            True,
            "solved",
            "no_response",
            _when(2024, 6, 3),
            _when(2024, 6, 3),
        ),
    ]


def _iso(at: datetime) -> str:
    return at.strftime("%Y-%m-%dT%H:%M:%SZ")


def macro_json(position: int, macro: Macro) -> dict[str, object]:
    macro_id = FIRST_ID + position
    html = "".join(f"<p>{p}</p>" for p in macro.paragraphs)
    return {
        "url": URL.format(id=macro_id),
        "id": macro_id,
        "title": macro.title,
        "active": True,
        "updated_at": _iso(macro.updated),
        "created_at": _iso(macro.created),
        "default": False,
        "position": position,
        "description": macro.description,
        "actions": [
            {"field": "comment_value_html", "value": html},
            {"field": "comment_mode_is_public", "value": str(macro.public).lower()},
            {"field": "status", "value": macro.status},
            {"field": "current_tags", "value": macro.tags},
        ],
        "restriction": None,
        "raw_title": macro.title,
    }


def build_zendesk(cases: dict[str, list[SeedCase]], policy: PolicyParams) -> dict[str, bytes]:
    items = [macro_json(i, m) for i, m in enumerate(macros(cases, policy))]
    export = {"macros": items, "next_page": None, "previous_page": None, "count": len(items)}
    return {"macros.json": (json.dumps(export, indent=2, ensure_ascii=False) + "\n").encode()}
