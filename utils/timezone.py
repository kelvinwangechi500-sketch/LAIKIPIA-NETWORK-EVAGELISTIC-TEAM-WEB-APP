from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


try:
    KENYA_TIMEZONE = ZoneInfo("Africa/Nairobi")
except ZoneInfoNotFoundError:
    # Keep local Windows deployments working when the optional tzdata package is absent.
    KENYA_TIMEZONE = timezone(timedelta(hours=3), name="EAT")


def to_kenya_time(value: datetime) -> datetime:
    """Convert a UTC database timestamp to East Africa Time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KENYA_TIMEZONE)