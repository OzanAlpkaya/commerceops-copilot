"""Lumora's campaign coupon calendar.

The seed gives coupon orders a code that was live on the order date, and the promotions
document (promo-codes-2026.pdf) is rendered from the same table, so the two agree.
"""

import re
from dataclasses import dataclass
from datetime import date

from mock_api.seed.rand import rng

MonthDay = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Campaign:
    code: str
    label: str  # how the promotions document names it, e.g. "Spring campaign"
    start: MonthDay  # inclusive
    end: MonthDay  # inclusive; before `start` when the campaign runs over New Year

    @property
    def percent(self) -> int:
        return coupon_percent(self.code)

    def live_on(self, d: date) -> bool:
        md = (d.month, d.day)
        if self.start <= self.end:
            return self.start <= md <= self.end
        return md >= self.start or md <= self.end

    def dates(self, year: int) -> tuple[date, date]:
        """The run that starts in `year`."""
        end_year = year if self.start <= self.end else year + 1
        return date(year, *self.start), date(end_year, *self.end)


# Seasonal campaigns, in calendar order. They never overlap.
SEASONAL: tuple[Campaign, ...] = (
    Campaign("SPRING15", "Spring campaign", (3, 1), (5, 31)),
    Campaign("SUMMER20", "Summer campaign", (6, 1), (8, 31)),
    Campaign("NEWHOME20", "New Home campaign", (9, 1), (10, 31)),
    Campaign("BF25", "Black Friday campaign", (11, 20), (12, 2)),
    Campaign("XMAS15", "Christmas campaign", (12, 3), (12, 24)),
    Campaign("BOXING25", "Boxing Day campaign", (12, 25), (1, 6)),
)
# Live all year; the only code outside the seasonal campaigns.
WELCOME = Campaign("WELCOME10", "Welcome code", (1, 1), (12, 31))


def coupon_percent(code: str) -> int:
    match = re.search(r"(\d+)$", code)
    if match is None:
        raise ValueError(f"Coupon code without a percentage: {code}")
    return int(match.group(1))


def seasonal_campaign(d: date) -> Campaign | None:
    return next((c for c in SEASONAL if c.live_on(d)), None)


def campaign_code(d: date, first_order: bool, seed: int, key: str) -> str:
    """A campaign coupon that was live on `d`; new customers often used WELCOME10."""
    seasonal = seasonal_campaign(d)
    if seasonal is None or (first_order and rng(seed, "welcome", key).random() < 0.5):
        return WELCOME.code
    return seasonal.code
