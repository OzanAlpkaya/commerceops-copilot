"""Inputs the documents are generated from: the client's policy parameters, the seed's
constants and a few fixed facts about the documents themselves."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from mock_api.policy import DEFAULT_PATH, PolicyParams, load_policy_params

# Publication dates printed on the documents ("Last updated ...").
V1_PUBLISHED = date(2024, 6, 1)
V2_PUBLISHED = date(2026, 2, 16)
SUPPORT_DOCS_PUBLISHED = date(2026, 2, 16)
PROMO_PUBLISHED = date(2025, 12, 15)
PROMO_YEAR = 2026

CONTACT_EMAIL = "support@lumorahome.example"
CHAT_HOURS = "Monday to Friday, 9:00–17:30"

# Supplier price lists in GBP are normalised to EUR at this fixed rate.
GBP_TO_EUR = Decimal("1.17")


def policy_params(path: Path = DEFAULT_PATH) -> PolicyParams:
    return load_policy_params(path)


def long_date(d: date) -> str:
    """1 March 2026"""
    return f"{d.day} {d:%B %Y}"


def day_month(d: date) -> str:
    """1 March"""
    return f"{d.day} {d:%B}"


def eur(amount: Decimal) -> str:
    """€4.95"""
    return f"€{amount:,.2f}"


def in_words(days: int) -> str:
    """14 -> "two weeks". Whole weeks are spelled out; anything else stays "N days"."""
    weeks = {1: "one week", 2: "two weeks", 3: "three weeks", 4: "four weeks"}
    if days % 7 == 0 and days // 7 in weeks:
        return weeks[days // 7]
    return f"{days} days"


def date_range(start: date, end: date) -> str:
    """25 December 2025 – 6 January 2026, or 1 March – 31 May 2026 within one year."""
    if start.year == end.year:
        return f"{day_month(start)} – {long_date(end)}"
    return f"{long_date(start)} – {long_date(end)}"
