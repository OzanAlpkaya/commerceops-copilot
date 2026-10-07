"""Moving Olist's 2016-2018 timeline so the newest order lands on the as-of date."""

from datetime import UTC, date, datetime, time, timedelta


def compute_offset(max_purchase: datetime, as_of: date) -> timedelta:
    """Whole weeks that move the newest purchase into the week ending on `as_of`.

    Whole weeks keep weekday patterns (Monday peaks stay on Mondays).
    """
    days = (as_of - max_purchase.date()).days
    if days < 0:
        raise ValueError(f"as_of {as_of} is before the newest purchase {max_purchase:%Y-%m-%d}")
    return timedelta(weeks=days // 7)


def end_of_day(d: date) -> datetime:
    """The seed's 'now': nothing it generates is later than this."""
    return datetime.combine(d, time(23, 59, 59), tzinfo=UTC)


def start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=UTC)


def shift(ts: datetime | None, offset: timedelta) -> datetime | None:
    return ts + offset if ts is not None else None


def past_only(ts: datetime | None, now: datetime) -> datetime | None:
    """Drop a timestamp that the shift pushed past 'now': that event has not happened yet."""
    return ts if ts is not None and ts <= now else None
