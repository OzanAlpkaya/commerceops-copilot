from datetime import date, timedelta

from mock_api.seed.campaigns import (
    SEASONAL,
    WELCOME,
    Campaign,
    campaign_code,
    coupon_percent,
    seasonal_campaign,
)


def test_campaign_codes_follow_the_calendar() -> None:
    assert campaign_code(date(2025, 11, 28), False, 1, "k") == "BF25"
    assert campaign_code(date(2025, 12, 26), False, 1, "k") == "BOXING25"
    assert campaign_code(date(2026, 4, 2), False, 1, "k") == "SPRING15"
    assert campaign_code(date(2026, 2, 10), False, 1, "k") == "WELCOME10"
    assert coupon_percent("SUMMER20") == 20


def test_boundaries() -> None:
    assert campaign_code(date(2025, 11, 19), False, 1, "k") == "WELCOME10"
    assert campaign_code(date(2025, 11, 20), False, 1, "k") == "BF25"
    assert campaign_code(date(2025, 12, 2), False, 1, "k") == "BF25"
    assert campaign_code(date(2025, 12, 3), False, 1, "k") == "XMAS15"
    assert campaign_code(date(2025, 12, 25), False, 1, "k") == "BOXING25"
    assert campaign_code(date(2026, 1, 6), False, 1, "k") == "BOXING25"
    assert campaign_code(date(2026, 1, 7), False, 1, "k") == "WELCOME10"


def test_seasonal_campaigns_never_overlap() -> None:
    day = date(2024, 1, 1)
    while day < date(2028, 1, 1):
        assert sum(c.live_on(day) for c in SEASONAL) <= 1, day
        day += timedelta(days=1)


def test_only_welcome_outside_seasonal_campaigns() -> None:
    gap = [date(2026, 1, 7), date(2026, 2, 28), date(2026, 11, 1), date(2026, 11, 19)]
    for day in gap:
        assert seasonal_campaign(day) is None
        assert campaign_code(day, False, 1, "k") == WELCOME.code


def test_new_year_run_ends_the_next_year() -> None:
    boxing = next(c for c in SEASONAL if c.code == "BOXING25")
    assert boxing.dates(2025) == (date(2025, 12, 25), date(2026, 1, 6))
    spring = Campaign("SPRING15", "Spring campaign", (3, 1), (5, 31))
    assert spring.dates(2026) == (date(2026, 3, 1), date(2026, 5, 31))
    assert boxing.percent == 25
