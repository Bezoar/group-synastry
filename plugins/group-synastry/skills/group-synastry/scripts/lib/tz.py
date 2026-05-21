"""IANA timezone resolution.

Per spec D7 / eval 1: timezone abbreviations like 'EDT', 'PST' must be rejected
and the user pointed at the IANA name. zoneinfo handles historical DST
correctly when given a real IANA zone name plus a wall-clock datetime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# Common abbreviations users type. We reject these so the skill can prompt for
# the IANA equivalent (per spec §14 edge-case table).
ABBREVIATION_HINTS = {
    "EDT": "America/New_York",
    "EST": "America/New_York",
    "CDT": "America/Chicago",
    "CST": "America/Chicago",
    "MDT": "America/Denver",
    "MST": "America/Denver",
    "PDT": "America/Los_Angeles",
    "PST": "America/Los_Angeles",
    "AKDT": "America/Anchorage",
    "AKST": "America/Anchorage",
    "HST": "Pacific/Honolulu",
    "BST": "Europe/London",
    "GMT": "Europe/London",
    "UTC": "UTC",
    "CET": "Europe/Paris",
    "CEST": "Europe/Paris",
    "IST": "Asia/Kolkata",  # India Standard Time most commonly meant
    "JST": "Asia/Tokyo",
    "AEST": "Australia/Sydney",
    "AEDT": "Australia/Sydney",
}


class TZError(ValueError):
    """Raised when the supplied string is not an acceptable IANA name."""


def normalize_tz(tz_str: str) -> str:
    """Return a valid IANA tz name or raise TZError with a helpful hint."""
    if not tz_str:
        raise TZError("Timezone is required (use an IANA name like 'America/New_York').")
    tz_str = tz_str.strip()
    try:
        ZoneInfo(tz_str)
        return tz_str
    except ZoneInfoNotFoundError:
        pass
    upper = tz_str.upper()
    hint = ABBREVIATION_HINTS.get(upper)
    if hint:
        raise TZError(
            f"'{tz_str}' is a timezone abbreviation, not an IANA name. "
            f"Use '{hint}' (or another IANA zone matching the birth location)."
        )
    raise TZError(
        f"'{tz_str}' is not a recognized IANA timezone. "
        "Use a name like 'America/New_York', 'Europe/Paris', or 'Asia/Tokyo'."
    )


class UTConversion(NamedTuple):
    ut_datetime: datetime  # tz-aware in UTC
    offset_hours: float    # local offset at the wall-clock instant
    julian_day_ut: float


def to_julian_day_ut(date_str: str, time_str: str, iana_tz: str) -> UTConversion:
    """Convert wall-clock local birth datetime to UT and Julian Day (UT).

    date_str: 'YYYY-MM-DD'
    time_str: 'HH:MM' (24h)
    iana_tz:  IANA name (already validated via normalize_tz)

    The Julian Day is computed using a Gregorian-to-JD formula valid for
    1582-10-15 onward; pre-Gregorian dates are rare in v1 and would need the
    Julian-calendar branch.
    """
    iana_tz = normalize_tz(iana_tz)
    naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    local = naive.replace(tzinfo=ZoneInfo(iana_tz))
    ut = local.astimezone(timezone.utc)
    offset = local.utcoffset()
    offset_hours = offset.total_seconds() / 3600.0 if offset else 0.0

    y, m, d = ut.year, ut.month, ut.day
    h = ut.hour + ut.minute / 60.0 + ut.second / 3600.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = (
        int(365.25 * (y + 4716))
        + int(30.6001 * (m + 1))
        + d
        + b
        - 1524.5
        + h / 24.0
    )
    return UTConversion(ut, offset_hours, jd)


def offset_at(date_str: str, time_str: str, iana_tz: str) -> str:
    """Return the local UTC offset at a given wall-clock instant as '+HH:MM'."""
    conv = to_julian_day_ut(date_str, time_str, iana_tz)
    h = conv.offset_hours
    sign = "+" if h >= 0 else "-"
    h = abs(h)
    hh = int(h)
    mm = int(round((h - hh) * 60))
    return f"{sign}{hh:02d}:{mm:02d}"
