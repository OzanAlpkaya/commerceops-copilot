from datetime import UTC, date, datetime, timedelta

import pytest

from mock_api.seed.dates import compute_offset, end_of_day, past_only


def test_offset_moves_newest_purchase_into_the_week_ending_on_as_of() -> None:
    newest = datetime(2018, 9, 3, 9, 6, tzinfo=UTC)
    as_of = date(2026, 10, 5)

    offset = compute_offset(newest, as_of)

    assert offset.days % 7 == 0
    shifted = (newest + offset).date()
    assert as_of - timedelta(days=6) <= shifted <= as_of
    assert offset.days == 2954  # 422 weeks: the real-data case from the plan


def test_offset_keeps_weekdays() -> None:
    newest = datetime(2018, 8, 29, 15, 0, tzinfo=UTC)
    for as_of in (date(2026, 10, 5), date(2026, 10, 9), date(2027, 1, 1)):
        assert (newest + compute_offset(newest, as_of)).weekday() == newest.weekday()


def test_policy_change_maps_back_to_late_january_2018() -> None:
    offset = compute_offset(datetime(2018, 9, 3, tzinfo=UTC), date(2026, 10, 5))
    assert (datetime(2026, 3, 1, tzinfo=UTC) - offset).date() == date(2018, 1, 28)


def test_as_of_before_data_is_rejected() -> None:
    with pytest.raises(ValueError):
        compute_offset(datetime(2018, 9, 3, tzinfo=UTC), date(2018, 1, 1))


def test_past_only_drops_future_events() -> None:
    now = end_of_day(date(2026, 10, 5))
    assert past_only(now, now) == now
    assert past_only(now + timedelta(seconds=1), now) is None
    assert past_only(None, now) is None
