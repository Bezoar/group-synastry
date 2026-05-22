"""Swiss Ephemeris wrapper with explicit per-body source selection.

Each body has a *best source* — the highest-accuracy ephemeris we have
available for it — and the wrapper requires that source unless the caller
opts into a fallback via ``force_source``. Silently degrading from Swiss Eph
to Keplerian (the prior behaviour) is forbidden because it makes eval results
non-reproducible: identical code on two machines returned different positions
depending on whether ``seas_18.se1`` happened to be on disk.

Source codes mirror evals/reference-charts.json's ``source_schema``:

* ``swisseph_builtin``     — Swiss Eph + Moshier (works without any files)
* ``swisseph_with_seas18`` — Swiss Eph + bundled ``seas_18.se1``
* ``keplerian_jpl_j2000``  — JPL J2000 osculating elements via ``lib/kepler.py``

The Swiss Eph data path is configured at module import to point at the
bundled directory plus any user-supplied dirs (see ``env.swisseph_data_paths``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    import swisseph as swe
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only when the dep is absent
    raise ModuleNotFoundError(
        "The 'pyswisseph' package is required but not installed. Install it with:\n"
        "    python -m pip install -r requirements.txt\n"
        "(run scripts/check_env.py from the skill directory for a full dependency check)."
    ) from exc

from . import env, kepler


# ---------------------------------------------------------------------------
# Module-load: configure Swiss Eph data path and probe which files are present
# ---------------------------------------------------------------------------

_EPHE_PATH = env.swisseph_path_string()
if _EPHE_PATH:
    swe.set_ephe_path(_EPHE_PATH)


def _file_available(name: str) -> bool:
    for d in env.swisseph_data_paths():
        if (d / name).exists():
            return True
    return False


EPHEMERIS_FILES = {
    "seas_18.se1": _file_available("seas_18.se1"),
}


_SWE_FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED


# Bodies always computed in a D6 natal chart.
ALWAYS_INCLUDED_PLANETS = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
    "Saturn", "Uranus", "Neptune", "Pluto",
    "Chiron", "Lilith", "Ceres", "Eris", "True Node",
)
ANGLES = ("Ascendant", "Midheaven", "Descendant", "IC", "Vertex")


# Swiss-Eph numeric IDs.
_SWE_BODIES = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "True Node": swe.TRUE_NODE,
    "Lilith": swe.MEAN_APOG,
    "Chiron": swe.CHIRON,
    "Ceres": swe.CERES,
    "Pallas": swe.PALLAS,
    "Juno": swe.JUNO,
    "Vesta": swe.VESTA,
    "Eris": swe.AST_OFFSET + 136199,  # asteroid (136199) Eris
}


# Per-body "best source" and the set of sources we'll accept under
# ``force_source``. The first entry of each list is the body's best source.
#
# Why Eris's best is keplerian_jpl_j2000: the bundled .se1 set does not
# include asteroid 136199 (it lives in a separate file, ``s136199s.se1``,
# that astro.com does not redistribute). The Keplerian fallback gives
# arcminute accuracy for Eris because it's a TNO with minimal perturbation.
_BODY_SOURCES: dict[str, list[str]] = {
    # Swiss Eph built-in is arcsecond-accurate for these — no file needed.
    "Sun":       ["swisseph_builtin"],
    "Moon":      ["swisseph_builtin"],
    "Mercury":   ["swisseph_builtin"],
    "Venus":     ["swisseph_builtin"],
    "Mars":      ["swisseph_builtin"],
    "Jupiter":   ["swisseph_builtin"],
    "Saturn":    ["swisseph_builtin"],
    "Uranus":    ["swisseph_builtin"],
    "Neptune":   ["swisseph_builtin"],
    "Pluto":     ["swisseph_builtin"],
    "True Node": ["swisseph_builtin"],
    "Lilith":    ["swisseph_builtin"],
    # Need seas_18.se1 for arcsec/arcmin accuracy; Keplerian as opt-in fallback.
    "Chiron":    ["swisseph_with_seas18", "keplerian_jpl_j2000"],
    "Ceres":     ["swisseph_with_seas18", "keplerian_jpl_j2000"],
    "Pallas":    ["swisseph_with_seas18", "keplerian_jpl_j2000"],
    "Juno":      ["swisseph_with_seas18", "keplerian_jpl_j2000"],
    "Vesta":     ["swisseph_with_seas18", "keplerian_jpl_j2000"],
    # No bundled Swiss-Eph file for (136199) Eris; Keplerian is the best
    # readily-available source.
    "Eris":      ["keplerian_jpl_j2000"],
}

# A source is "usable" if its prerequisites are met.
_SOURCE_REQUIRES_FILE = {
    "swisseph_builtin":     None,
    "swisseph_with_seas18": "seas_18.se1",
    "keplerian_jpl_j2000":  None,  # bundled Python implementation
}


class EphemerisFileMissing(RuntimeError):
    """Raised when a body's best source requires a Swiss Eph file we lack."""


def _source_is_available(source: str) -> bool:
    f = _SOURCE_REQUIRES_FILE.get(source)
    return f is None or EPHEMERIS_FILES.get(f, False)


def best_source(body: str) -> str:
    """Return the best ephemeris source for *body* given files on disk.

    Raises ``EphemerisFileMissing`` if the body's preferred source requires
    a file we don't have. Callers that want to opt into a fallback must pass
    ``force_source=...`` to :func:`calc_body`.
    """
    if body not in _BODY_SOURCES:
        raise ValueError(f"Unknown body: {body}")
    preferred = _BODY_SOURCES[body][0]
    if _source_is_available(preferred):
        return preferred
    raise EphemerisFileMissing(
        f"Body {body!r} requires source {preferred!r} but the file "
        f"{_SOURCE_REQUIRES_FILE[preferred]!r} was not found in any of "
        f"{[str(p) for p in env.swisseph_data_paths()]!r}. Pass "
        f"force_source={_BODY_SOURCES[body][-1]!r} to fall back."
    )


KEPLERIAN_NAMES = {"Chiron", "Ceres", "Pallas", "Juno", "Vesta", "Eris"}


@dataclass
class BodyPosition:
    name: str
    longitude: float        # ecliptic longitude in degrees [0, 360)
    speed: float            # degrees/day; negative => retrograde
    source: str             # one of the codes in _SOURCE_REQUIRES_FILE

    @property
    def retrograde(self) -> bool:
        return self.speed < 0


@dataclass
class HouseChart:
    cusps: tuple              # 12 cusps in ecliptic longitude
    ascendant: float
    midheaven: float
    descendant: float
    ic: float
    vertex: float
    house_system: str         # "placidus", "whole-sign", etc.


HOUSE_SYSTEM_CODES = {
    "placidus": b"P",
    "koch": b"K",
    "whole-sign": b"W",
    "equal": b"E",
    "porphyry": b"O",
    "regiomontanus": b"R",
    "campanus": b"C",
}


def _calc_swisseph(jd_ut: float, name: str, sidereal_flag: int) -> tuple[float, float]:
    flags = _SWE_FLAGS | sidereal_flag
    pos, _ret = swe.calc_ut(jd_ut, _SWE_BODIES[name], flags)
    return pos[0] % 360.0, pos[3]


def _calc_keplerian(jd_ut: float, name: str) -> tuple[float, float]:
    lon = kepler.geocentric_longitude(name, jd_ut)
    lon_next = kepler.geocentric_longitude(name, jd_ut + 1.0)
    # Two-step finite difference, wrapping across 360°.
    speed = ((lon_next - lon + 540.0) % 360.0) - 180.0
    return lon, speed


def calc_body(
    jd_ut: float,
    name: str,
    *,
    sidereal_flag: int = 0,
    force_source: Optional[str] = None,
) -> BodyPosition:
    """Compute ecliptic longitude and speed for *name* at *jd_ut*.

    By default uses the body's best available source (see :func:`best_source`).
    Tests and evals that need to pin a specific source (e.g. to keep results
    reproducible across machines with different Swiss Eph files) can pass
    ``force_source``; the value must be one of the codes listed for *name* in
    :data:`_BODY_SOURCES`.
    """
    if name not in _SWE_BODIES:
        raise ValueError(f"Unknown body: {name}")
    if force_source is not None:
        allowed = _BODY_SOURCES.get(name, [])
        if force_source not in allowed:
            raise ValueError(
                f"force_source={force_source!r} not allowed for body {name!r}; "
                f"choose from {allowed!r}."
            )
        if not _source_is_available(force_source):
            raise EphemerisFileMissing(
                f"force_source={force_source!r} requires "
                f"{_SOURCE_REQUIRES_FILE[force_source]!r} which is not present."
            )
        source = force_source
    else:
        source = best_source(name)

    if source.startswith("swisseph"):
        lon, speed = _calc_swisseph(jd_ut, name, sidereal_flag)
    elif source == "keplerian_jpl_j2000":
        if sidereal_flag:
            # Keplerian path is tropical; caller must subtract ayanamsa.
            raise ValueError(
                "sidereal_flag is not supported on the Keplerian path; "
                "subtract the ayanamsa from the tropical longitude instead."
            )
        lon, speed = _calc_keplerian(jd_ut, name)
    else:  # pragma: no cover — guarded by the validation above
        raise AssertionError(f"unreachable source: {source}")
    return BodyPosition(name, lon, speed, source)


def south_node(north_node_lon: float) -> float:
    return (north_node_lon + 180.0) % 360.0


def calc_houses(jd_ut: float, lat: float, lon: float, system: str = "placidus") -> HouseChart:
    code = HOUSE_SYSTEM_CODES.get(system.lower())
    if code is None:
        raise ValueError(
            f"Unknown house system: {system}. "
            f"Expected one of: {sorted(HOUSE_SYSTEM_CODES)}"
        )
    cusps, ascmc = swe.houses(jd_ut, lat, lon, code)
    asc = ascmc[0]
    mc = ascmc[1]
    return HouseChart(
        cusps=tuple(c % 360.0 for c in cusps),
        ascendant=asc,
        midheaven=mc,
        descendant=(asc + 180.0) % 360.0,
        ic=(mc + 180.0) % 360.0,
        vertex=ascmc[3] % 360.0,
        house_system=system.lower(),
    )


def assign_house(planet_lon: float, cusps: tuple) -> int:
    """Return 1..12 — which house the planet falls in given the 12 cusps."""
    for i in range(12):
        c1 = cusps[i]
        c2 = cusps[(i + 1) % 12]
        if c2 < c1:
            c2 += 360.0
        p = planet_lon
        if p < c1:
            p += 360.0
        if c1 <= p < c2:
            return i + 1
    return 12  # numerical fallback; should not normally reach here
