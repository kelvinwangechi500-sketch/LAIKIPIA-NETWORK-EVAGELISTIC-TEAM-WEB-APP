from datetime import datetime, timezone
from zoneinfo import ZoneInfo


KENYA_TIMEZONE = ZoneInfo("Africa/Nairobi")


def to_kenya_time(value: datetime) -> datetime:
    """Convert a UTC database timestamp to East Africa Time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KENYA_TIMEZONE)