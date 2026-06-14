"""Vedic (sidereal) astrology computation layer.

Sidereal positions (Lahiri ayanamsa by default), the 27 **nakshatras** (+ pada
and Vimshottari lord), and Whole-Sign **rasi** houses from the sidereal
Ascendant. This is a distinct paradigm from the Western/medieval substrate, so it
shares little with ``lib/medieval``.

Sidereal longitude is the canonical Vedic definition ``(tropical − ayanamsa)``;
this matches swisseph's native sidereal mode to < 0.01° (see test_vedic).

Computation only — no interpretation prose. The Vimshottari dasha **timeline**
and the **Navamsa (D9)** divisional chart are the deferred heavy pieces.

Reference data verified, not recalled: the 27 nakshatra names + order and the
Vimshottari lord cycle (Wikipedia "Nakshatra"; the 9-lord cycle repeats cleanly
3× across the 27, which the integrity test pins). Ayanamsa values come from
swisseph itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import swisseph as swe

if __package__ in (None, ""):
    import formatting  # type: ignore[import-not-found]
else:
    from . import formatting

SIGNS = formatting.SIGNS


# ---------------------------------------------------------------------------
# Ayanamsa + sidereal conversion
# ---------------------------------------------------------------------------
# Swiss Ephemeris sidereal-mode constants for the supported ayanamsas.
AYANAMSAS = {
    "lahiri": swe.SIDM_LAHIRI,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "raman": swe.SIDM_RAMAN,
    "fagan-bradley": swe.SIDM_FAGAN_BRADLEY,
    "true-chitra": swe.SIDM_TRUE_CITRA,
}
DEFAULT_AYANAMSA = "lahiri"


def ayanamsa(jd_ut: float, mode: str = DEFAULT_AYANAMSA) -> float:
    """The ayanamsa (degrees) at *jd_ut* for the given mode (default Lahiri)."""
    sid = AYANAMSAS.get(mode)
    if sid is None:
        raise ValueError(f"unknown ayanamsa {mode!r}; choose from {sorted(AYANAMSAS)}")
    swe.set_sid_mode(sid)
    return swe.get_ayanamsa_ut(jd_ut)


def to_sidereal(tropical_lon: float, jd_ut: float, mode: str = DEFAULT_AYANAMSA) -> float:
    """Sidereal longitude = (tropical − ayanamsa) mod 360 — the canonical Vedic value."""
    return (tropical_lon - ayanamsa(jd_ut, mode)) % 360.0


# ---------------------------------------------------------------------------
# Nakshatras (27 lunar mansions)
# ---------------------------------------------------------------------------
NAKSHATRA_SPAN = 360.0 / 27.0   # 13°20'
PADA_SPAN = NAKSHATRA_SPAN / 4.0  # 3°20'

# Order from 0° sidereal Aries. Source: Wikipedia "Nakshatra".
NAKSHATRAS = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishtha", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
)

# The Vimshottari dasha lord cycle (9), repeated 3× across the 27 nakshatras.
VIMSHOTTARI_CYCLE = (
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
)


@dataclass
class NakshatraPosition:
    index: int    # 0..26
    name: str
    pada: int     # 1..4
    lord: str     # Vimshottari ruling planet


def nakshatra_of(sidereal_lon: float) -> NakshatraPosition:
    """The nakshatra, pada (1..4), and Vimshottari lord of a sidereal longitude."""
    lon = sidereal_lon % 360.0
    idx = min(int(lon // NAKSHATRA_SPAN), 26)
    within = lon - idx * NAKSHATRA_SPAN
    pada = min(int(within // PADA_SPAN) + 1, 4)
    return NakshatraPosition(idx, NAKSHATRAS[idx], pada, VIMSHOTTARI_CYCLE[idx % 9])


# ---------------------------------------------------------------------------
# Whole-Sign rasi houses
# ---------------------------------------------------------------------------

def rasi_house(planet_sidereal_lon: float, asc_sidereal_lon: float) -> int:
    """Whole-sign rasi house (1..12): the sidereal rising sign is house 1,
    counting forward one whole sign per house (shared whole-sign helper)."""
    return formatting.whole_sign_house(planet_sidereal_lon, asc_sidereal_lon)


# ---------------------------------------------------------------------------
# Assembly — a Vedic sidereal natal chart
# ---------------------------------------------------------------------------
# The nine grahas in the traditional order; Rahu/Ketu are the lunar nodes
# (True Node / its opposite). The modern planets are not classical grahas.
VEDIC_GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
_GRAHA_SOURCE = {"Rahu": "True Node", "Ketu": "South Node"}


@dataclass
class GrahaPosition:
    name: str
    sidereal_longitude: float
    sign: str
    rasi_house: int
    nakshatra: str
    pada: int
    lord: str
    retrograde: bool


@dataclass
class SiderealAscendant:
    longitude: float
    sign: str
    nakshatra: str
    pada: int


@dataclass
class VedicChart:
    natal: object          # tropical reference chart
    ayanamsa_mode: str
    ayanamsa_value: float
    ascendant: SiderealAscendant
    grahas: list           # list[GrahaPosition]
    moon_nakshatra: NakshatraPosition  # the janma (birth) nakshatra

    def to_dict(self) -> dict:
        return {
            "kind": "vedic",
            "natal": self.natal.to_dict(),
            "ayanamsa_mode": self.ayanamsa_mode,
            "ayanamsa_value": self.ayanamsa_value,
            "ascendant": asdict(self.ascendant),
            "grahas": [asdict(g) for g in self.grahas],
            "moon_nakshatra": asdict(self.moon_nakshatra),
        }


def compute_vedic(person: dict, ayanamsa_mode: str = DEFAULT_AYANAMSA,
                  house_system: str = "whole-sign") -> VedicChart:
    """Compute a Vedic sidereal natal chart: sidereal graha positions (Lahiri by
    default), nakshatra/pada/lord, and Whole-Sign rasi houses from the sidereal
    Ascendant. Computation only — no Vimshottari dasha timeline or Navamsa yet."""
    # Lazy import of the natal engine. chart.py is a top-level script in
    # scripts/: it resolves as `chart` when scripts/ is on sys.path (CLI + test
    # harness) and as `..chart` under package invocation (scripts.lib.vedic).
    # Handle both, per the dual-invocation contract used across the package.
    try:
        from .. import chart as chart_mod  # type: ignore[no-redef]
    except (ImportError, ValueError):
        import chart as chart_mod  # type: ignore[import-not-found,no-redef]

    # house_system only affects the embedded tropical reference chart's cusps;
    # Vedic surfaces whole-sign *rasi* houses from the sidereal Ascendant (see
    # rasi_house), so it never changes our output. Kept for signature-symmetry
    # with compute_natal/compute_medieval; not exposed on the CLI. (refactor-todo: C)
    natal = chart_mod.compute_natal(person, house_system=house_system)
    jd = natal.julian_day_ut
    ay = ayanamsa(jd, ayanamsa_mode)

    def sid(lon: float) -> float:
        return (lon - ay) % 360.0

    asc = next(a for a in natal.angles if a.name == "Ascendant")
    asc_sid = sid(asc.longitude)
    asc_nak = nakshatra_of(asc_sid)
    ascendant = SiderealAscendant(asc_sid, formatting.sign_of(asc_sid), asc_nak.name, asc_nak.pada)

    by_name = {p.name: p for p in natal.planets}
    grahas: list = []
    moon_nak = None
    for g in VEDIC_GRAHAS:
        pe = by_name[_GRAHA_SOURCE.get(g, g)]
        s = sid(pe.longitude)
        nak = nakshatra_of(s)
        grahas.append(GrahaPosition(
            g, s, formatting.sign_of(s), rasi_house(s, asc_sid), nak.name, nak.pada, nak.lord, pe.retrograde
        ))
        if g == "Moon":
            moon_nak = nak
    return VedicChart(natal, ayanamsa_mode, ay, ascendant, grahas, moon_nak)
