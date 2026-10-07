"""Vocabulary rules for the corpus: the team's jargon (D9) and what must never appear (D10)."""

import re

# D9: abbreviations used bare in Slack and Zendesk, with their meanings. A text that uses
# an abbreviation never also contains one of its expansions.
GLOSSARY: dict[str, str] = {
    "RMA": "return merchandise authorisation (a return number)",
    "RTS": "returned to sender",
    "DOA": "defective on arrival",
    "OOW": "out of window (outside the return window)",
    "SC": "store credit",
}
EXPANSIONS: dict[str, tuple[str, ...]] = {
    "RMA": ("return merchandise", "return material", "return authori"),
    "RTS": ("returned to sender", "return to sender"),
    "DOA": ("dead on arrival", "defective on arrival"),
    "OOW": ("out of window", "out of the window", "outside the window", "outside the 30-day"),
    "SC": ("store credit",),
}

# D10: topics deliberately absent from every document.
ABSENT_TOPICS: tuple[str, ...] = (
    "price matching",
    "gift wrapping",
    "shipping outside Ireland",
    "extended warranties",
)
FORBIDDEN: tuple[str, ...] = (
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
    # Statutory periods: they would resolve D4 and contradict the 30-day rules.
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


def uses(abbreviation: str, text: str) -> bool:
    return re.search(rf"\b{abbreviation}\b", text) is not None


def expands(abbreviation: str, text: str) -> bool:
    lowered = text.lower()
    return any(e in lowered for e in EXPANSIONS[abbreviation])


def forbidden_in(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in FORBIDDEN if term in lowered]
