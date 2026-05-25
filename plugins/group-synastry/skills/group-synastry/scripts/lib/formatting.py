"""Degree formatting and zodiac sign helpers."""
from __future__ import annotations

from typing import NamedTuple


SIGNS = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)
GLYPHS = {
    "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
    "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
    "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓",
}
PLANET_GLYPHS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀",
    "Mars": "♂", "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅",
    "Neptune": "♆", "Pluto": "♇", "Chiron": "⚷",
    "True Node": "☊", "South Node": "☋",
    "Ceres": "⚳", "Eris": "⯰", "Lilith": "⚸",
    "Ascendant": "ASC", "Midheaven": "MC", "Vertex": "Vx",
}


class Position(NamedTuple):
    sign: str
    degree: int   # 0-29
    minute: int   # 0-59
    second: int   # 0-59
    raw: float    # original ecliptic longitude in degrees [0, 360)


def normalize_longitude(lon: float) -> float:
    return lon % 360.0


def split_longitude_exact(lon: float) -> Position:
    """Exact split: degree, FLOORED arc-minute, and the residual arc-second.

    This is the split behind every position shown in a chart (charts display
    arc-seconds, so the floored minute is exactly correct — the remainder lands
    in the seconds field, with no rounding bias). :func:`split_longitude` is the
    rounded variant, kept only for minute-only summaries.
    """
    lon = normalize_longitude(lon)
    sign_index = int(lon // 30)
    in_sign = lon - 30 * sign_index
    deg = int(in_sign)
    minutes_full = (in_sign - deg) * 60
    mins = int(minutes_full)
    secs = int(round((minutes_full - mins) * 60))
    if secs == 60:
        secs = 0
        mins += 1
    if mins == 60:
        mins = 0
        deg += 1
    if deg == 30:
        deg = 0
        sign_index = (sign_index + 1) % 12
    return Position(SIGNS[sign_index], deg, mins, secs, lon)


def split_longitude(lon: float) -> Position:
    """Split a longitude into sign/degree/arc-minute, **rounded to the nearest
    arc-minute**, for minute-only summaries (no arc-seconds shown).

    When seconds are omitted, rounding (not flooring) avoids a systematic
    downward bias: e.g. 24°38'41" reads as 24° Gemini 39', not 38'. The
    ``second`` field is 0 by construction here. Chart tables show arc-seconds
    and use :func:`split_longitude_exact` instead; this variant remains for the
    minute-only :func:`format_position` path.
    """
    lon = normalize_longitude(lon)
    sign_index = int(lon // 30)
    in_sign = lon - 30 * sign_index
    deg = int(in_sign)
    minute = int(round((in_sign - deg) * 60))
    if minute == 60:
        minute = 0
        deg += 1
    if deg == 30:
        deg = 0
        sign_index = (sign_index + 1) % 12
    return Position(SIGNS[sign_index], deg, minute, 0, lon)


def format_position(lon: float, retrograde: bool = False, with_seconds: bool = False) -> str:
    """Format an ecliptic longitude as e.g. \"10° Taurus 53'\" or with seconds."""
    p = split_longitude_exact(lon) if with_seconds else split_longitude(lon)
    base = f"{p.degree}° {p.sign} {p.minute:02d}'"
    if with_seconds:
        base = f"{p.degree}° {p.sign} {p.minute:02d}' {p.second:02d}\""
    if retrograde:
        base += " R"
    return base


def format_position_glyph(lon: float, retrograde: bool = False) -> str:
    """Render a longitude as a chart-table position with the sign glyph and
    arc-second precision, e.g. ``24° ♊ Gemini 38' 41\"``.

    Uses :func:`split_longitude_exact`, so the arc-minute is floored and the
    remainder shows as arc-seconds — exact, with no rounding bias. This is the
    single source of truth for position strings in the Markdown renderer.
    """
    p = split_longitude_exact(lon)
    glyph = GLYPHS.get(p.sign, "")
    base = f"{p.degree}° {glyph} {p.sign} {p.minute:02d}' {p.second:02d}\""
    if retrograde:
        base += " R"
    return base


def aspect_from_separation(sep_deg: float):
    """Classify a separation (0..180) into an aspect or return None.

    Default orbs from spec settings. Returns (name, exact_angle, orb).
    """
    sep = abs(sep_deg) % 360.0
    if sep > 180:
        sep = 360 - sep
    table = [
        ("conjunction", 0.0, 8.0),
        ("opposition", 180.0, 8.0),
        ("trine", 120.0, 7.0),
        ("square", 90.0, 7.0),
        ("sextile", 60.0, 5.0),
        ("quincunx", 150.0, 3.0),
        ("semisextile", 30.0, 2.0),
        ("semisquare", 45.0, 2.0),
        ("sesquisquare", 135.0, 2.0),
    ]
    best = None
    for name, exact, orb in table:
        delta = abs(sep - exact)
        if delta <= orb and (best is None or delta < best[2]):
            best = (name, exact, delta)
    return best  # (name, exact_angle, orb_deg) or None


def format_orb(orb_deg: float) -> str:
    deg = int(orb_deg)
    minutes = int(round((orb_deg - deg) * 60))
    if minutes == 60:
        minutes = 0
        deg += 1
    return f"{deg}°{minutes:02d}'"


def shorter_arc_midpoint(lon_a: float, lon_b: float) -> float:
    """Return the midpoint of two ecliptic longitudes along the shorter arc."""
    a = normalize_longitude(lon_a)
    b = normalize_longitude(lon_b)
    diff = (b - a) % 360.0
    if diff > 180.0:
        # b is "behind" a along the short arc; midpoint goes the other way
        return normalize_longitude(a + (diff - 360.0) / 2.0)
    return normalize_longitude(a + diff / 2.0)
