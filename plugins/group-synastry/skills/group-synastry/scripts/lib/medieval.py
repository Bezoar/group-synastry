"""Medieval / traditional-European computation layer.

Deterministic substrate for the medieval track specified in
``docs/specs/medieval.md`` §3: **sect**, **essential dignities** (+ almuten), and
the **Lots** of Fortune & Spirit. Everything here is arithmetic and verified
lookup tables layered on positions already produced by ``lib/ephem`` /
``chart.compute_natal`` — no model-generated values (spec §2).

Interpretation prose and citations are NOT produced here; this module only
computes. The citation corpus is a separate sub-project (``docs/research/biblio.md``).

Reference tables in this module were cross-checked against authoritative sources,
never reproduced from memory (spec §4). Sources are cited at each table.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Optional

if __package__ in (None, ""):
    import formatting  # type: ignore[import-not-found]
else:
    from . import formatting

SIGNS = formatting.SIGNS  # ("Aries", ..., "Pisces"); index 0..11

# ---------------------------------------------------------------------------
# Sect
# ---------------------------------------------------------------------------
# Sect is the day/night division that conditions much of traditional practice
# (triplicity rulers, the benefic/malefic "of the sect", lot reversals). A chart
# is diurnal when the Sun is above the horizon, nocturnal when below.

DIURNAL = "diurnal"
NOCTURNAL = "nocturnal"

_SECTS = (DIURNAL, NOCTURNAL)

# Planets belonging to each sect (the luminaries lead them). Mercury is not
# fixed — it takes the sect of the half of the sky it is in relative to the Sun
# (oriental -> diurnal, occidental -> nocturnal); see :func:`orientality`.
_DIURNAL_PLANETS = {"Sun", "Jupiter", "Saturn"}
_NOCTURNAL_PLANETS = {"Moon", "Venus", "Mars"}


def _check_sect(sect: str) -> str:
    if sect not in _SECTS:
        raise ValueError(f"sect must be one of {_SECTS!r}, got {sect!r}")
    return sect


def determine_sect(sun_lon: float, asc_lon: float) -> str:
    """Return ``DIURNAL`` or ``NOCTURNAL`` from the Sun's position vs the horizon.

    The horizon is the Ascendant–Descendant axis. Measuring the Sun's zodiacal
    distance ahead of the Ascendant, ``d = (sun - asc) mod 360``: the lower
    hemisphere (houses 1–6, below the horizon) spans ``d`` in (0, 180], and the
    upper hemisphere (houses 7–12, above the horizon) spans (180, 360). The Sun
    exactly on the Ascendant (sunrise, ``d == 0``) counts as day.
    """
    d = (sun_lon - asc_lon) % 360.0
    above_horizon = d == 0.0 or d > 180.0
    return DIURNAL if above_horizon else NOCTURNAL


def chart_sect(chart) -> str:
    """Sect of a computed :class:`chart.NatalChart` (needs Sun and Ascendant).

    Raises ``ValueError`` if the chart has no Ascendant (e.g. an unknown birth
    time) — sect is undefined without the horizon.
    """
    sun = next((p for p in chart.planets if p.name == "Sun"), None)
    asc = next((a for a in chart.angles if a.name == "Ascendant"), None)
    if sun is None:
        raise ValueError("chart has no Sun position")
    if asc is None:
        raise ValueError("chart has no Ascendant — sect needs an accurate birth time")
    return determine_sect(sun.longitude, asc.longitude)


def sect_light(sect: str) -> str:
    """The luminary 'of the sect' — Sun by day, Moon by night."""
    return "Sun" if _check_sect(sect) == DIURNAL else "Moon"


def benefic_of_sect(sect: str) -> str:
    """The benefic that acts most favourably in this sect (Jupiter day / Venus night)."""
    return "Jupiter" if _check_sect(sect) == DIURNAL else "Venus"


def malefic_of_sect(sect: str) -> str:
    """The in-sect (less harmful) malefic — Saturn by day, Mars by night."""
    return "Saturn" if _check_sect(sect) == DIURNAL else "Mars"


def contrary_malefic(sect: str) -> str:
    """The out-of-sect (more harmful) malefic — Mars by day, Saturn by night."""
    return "Mars" if _check_sect(sect) == DIURNAL else "Saturn"


def planet_sect(planet: str):
    """The fixed sect of a planet, or ``None`` for Mercury (sect by orientality)."""
    if planet in _DIURNAL_PLANETS:
        return DIURNAL
    if planet in _NOCTURNAL_PLANETS:
        return NOCTURNAL
    return None


def orientality(planet_lon: float, sun_lon: float) -> str:
    """'oriental' (morning star, rises before the Sun) or 'occidental' (evening star).

    A planet 'behind' the Sun in zodiacal order rises before it. With
    ``diff = (sun - planet) mod 360``, ``diff`` in (0, 180] is oriental.
    """
    diff = (sun_lon - planet_lon) % 360.0
    return "oriental" if 0.0 < diff <= 180.0 else "occidental"


# ---------------------------------------------------------------------------
# Essential dignities — verified reference tables
# ---------------------------------------------------------------------------
# These five tables are the highest factual-accuracy risk in the module
# (spec §4) and were cross-checked against authoritative sources, NOT recalled.
# Sources are cited per table. The medieval default uses the EGYPTIAN terms and
# the Dorothean triplicities; a Ptolemaic variant is a future addition (§4).

# Traditional 7-planet domicile rulerships (universal; Wikipedia "Essential
# dignity" rulership/detriment table).
DOMICILE = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

# Exaltation: sign -> (planet, exact degree). Sources: Wikipedia
# "Exaltation (astrology)", cross-checked github.com/flatangle/flatlib — agree
# exactly. Signs absent here have no classical exaltation.
EXALTATION = {
    "Aries": ("Sun", 19), "Taurus": ("Moon", 3), "Cancer": ("Jupiter", 15),
    "Virgo": ("Mercury", 15), "Libra": ("Saturn", 21), "Capricorn": ("Mars", 28),
    "Pisces": ("Venus", 27),
}

# Element membership and Dorothean triplicity rulers (day / night /
# participating). Source: Wikipedia "Triplicity" (internally consistent by
# element). Only the sect ruler (day OR night) scores the +3; the participating
# ruler is a minor co-ruler, exposed but not scored.
ELEMENTS = {
    "Fire": ("Aries", "Leo", "Sagittarius"),
    "Earth": ("Taurus", "Virgo", "Capricorn"),
    "Air": ("Gemini", "Libra", "Aquarius"),
    "Water": ("Cancer", "Scorpio", "Pisces"),
}
TRIPLICITY = {
    "Fire":  {"day": "Sun",   "night": "Jupiter", "participating": "Saturn"},
    "Earth": {"day": "Venus", "night": "Moon",    "participating": "Mars"},
    "Air":   {"day": "Saturn", "night": "Mercury", "participating": "Jupiter"},
    "Water": {"day": "Venus", "night": "Mars",    "participating": "Moon"},
}

# Egyptian terms (bounds): sign -> ordered [(planet, end_degree)], cumulative to
# 30°. Source: github.com/flatangle/flatlib tables.py. Cross-checks: the Aquarius
# row (kiraryberg.com/blog/the-bounds) and the Aries distribution (web search)
# match; every row sums to 30°. NB this is the EGYPTIAN set — distinct from the
# Ptolemaic terms (e.g. skyscript.co.uk gives Aries Venus 6–14, the Ptolemaic
# value, vs Egyptian 6–12).
EGYPTIAN_TERMS = {
    "Aries":       [("Jupiter", 6), ("Venus", 12), ("Mercury", 20), ("Mars", 25), ("Saturn", 30)],
    "Taurus":      [("Venus", 8), ("Mercury", 14), ("Jupiter", 22), ("Saturn", 27), ("Mars", 30)],
    "Gemini":      [("Mercury", 6), ("Jupiter", 12), ("Venus", 17), ("Mars", 24), ("Saturn", 30)],
    "Cancer":      [("Mars", 7), ("Venus", 13), ("Mercury", 19), ("Jupiter", 26), ("Saturn", 30)],
    "Leo":         [("Jupiter", 6), ("Venus", 11), ("Saturn", 18), ("Mercury", 24), ("Mars", 30)],
    "Virgo":       [("Mercury", 7), ("Venus", 17), ("Jupiter", 21), ("Mars", 28), ("Saturn", 30)],
    "Libra":       [("Saturn", 6), ("Mercury", 14), ("Jupiter", 21), ("Venus", 28), ("Mars", 30)],
    "Scorpio":     [("Mars", 7), ("Venus", 11), ("Mercury", 19), ("Jupiter", 24), ("Saturn", 30)],
    "Sagittarius": [("Jupiter", 12), ("Venus", 17), ("Mercury", 21), ("Saturn", 26), ("Mars", 30)],
    "Capricorn":   [("Mercury", 7), ("Jupiter", 14), ("Venus", 22), ("Saturn", 26), ("Mars", 30)],
    "Aquarius":    [("Mercury", 7), ("Venus", 13), ("Jupiter", 20), ("Mars", 25), ("Saturn", 30)],
    "Pisces":      [("Venus", 12), ("Jupiter", 16), ("Mercury", 19), ("Mars", 28), ("Saturn", 30)],
}

# Chaldean faces / decans: sign -> [first 0–10°, second 10–20°, third 20–30°].
# Source: github.com/flatangle/flatlib tables.py; follows the continuous
# Chaldean order; the Aries first face (Mars) matches skyscript.co.uk.
FACES = {
    "Aries": ["Mars", "Sun", "Venus"],
    "Taurus": ["Mercury", "Moon", "Saturn"],
    "Gemini": ["Jupiter", "Mars", "Sun"],
    "Cancer": ["Venus", "Mercury", "Moon"],
    "Leo": ["Saturn", "Jupiter", "Mars"],
    "Virgo": ["Sun", "Venus", "Mercury"],
    "Libra": ["Moon", "Saturn", "Jupiter"],
    "Scorpio": ["Mars", "Sun", "Venus"],
    "Sagittarius": ["Mercury", "Moon", "Saturn"],
    "Capricorn": ["Jupiter", "Mars", "Sun"],
    "Aquarius": ["Venus", "Mercury", "Moon"],
    "Pisces": ["Saturn", "Jupiter", "Mars"],
}

# Dignity point-scores (Lilly's table; Wikipedia "Essential dignity" gives the
# same: domicile +5, exaltation +4, triplicity +3, terms +2, face +1).
DIGNITY_POINTS = {"domicile": 5, "exaltation": 4, "triplicity": 3, "term": 2, "face": 1}
_DIGNITY_ORDER = ("domicile", "exaltation", "triplicity", "term", "face")

# Chaldean order (slowest/highest to fastest), used only as a deterministic
# final tie-break for the almuten.
_CHALDEAN_ORDER = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")

# Fall: a planet is in fall in the sign opposite its exaltation.
_FALL = {
    SIGNS[(SIGNS.index(sign) + 6) % 12]: planet
    for sign, (planet, _deg) in EXALTATION.items()
}


# ---------------------------------------------------------------------------
# Essential dignities — accessors
# ---------------------------------------------------------------------------

def sign_of(lon: float) -> str:
    return formatting.sign_of(lon)


def _degrees_in_sign(lon: float) -> float:
    return (lon % 360.0) % 30.0


def domicile_ruler(sign: str) -> str:
    return DOMICILE[sign]


def exaltation(sign: str):
    """``(planet, degree)`` exalted in *sign*, or ``None``."""
    return EXALTATION.get(sign)


def exaltation_ruler(sign: str):
    e = EXALTATION.get(sign)
    return e[0] if e else None


def _element_of(sign: str) -> str:
    for element, signs in ELEMENTS.items():
        if sign in signs:
            return element
    raise ValueError(f"unknown sign: {sign}")


def triplicity_ruler(sign: str, sect: str) -> str:
    """The triplicity ruler 'of the time' — day ruler by day, night by night."""
    key = "day" if _check_sect(sect) == DIURNAL else "night"
    return TRIPLICITY[_element_of(sign)][key]


def triplicity_participating(sign: str) -> str:
    return TRIPLICITY[_element_of(sign)]["participating"]


def term_ruler(lon: float) -> str:
    sign = sign_of(lon)
    d = _degrees_in_sign(lon)
    for planet, end in EGYPTIAN_TERMS[sign]:
        if d < end:
            return planet
    return EGYPTIAN_TERMS[sign][-1][0]  # exactly 30° guards to the last term


def face_ruler(lon: float) -> str:
    sign = sign_of(lon)
    idx = min(int(_degrees_in_sign(lon) // 10), 2)
    return FACES[sign][idx]


def detriment_ruler(sign: str) -> str:
    """Ruler of the opposite sign — the planet in detriment here."""
    return DOMICILE[SIGNS[(SIGNS.index(sign) + 6) % 12]]


def is_detriment(planet: str, sign: str) -> bool:
    return detriment_ruler(sign) == planet


def fall_ruler(sign: str):
    """The planet in fall in *sign* (opposite its exaltation), or ``None``."""
    return _FALL.get(sign)


def is_fall(planet: str, sign: str) -> bool:
    return _FALL.get(sign) == planet


# ---------------------------------------------------------------------------
# Essential dignities — per-planet state and almuten
# ---------------------------------------------------------------------------

@dataclass
class DignityState:
    planet: str
    sign: str
    dignities: list[str]   # held, ordered by descending point value
    detriment: bool
    fall: bool
    peregrine: bool        # holds no dignity AND not in detriment/fall
    score: int             # sum of points for the dignities held


def dignities_of(planet: str, lon: float, sect: str) -> DignityState:
    """Which essential dignities *planet* holds at *lon*, with its score/state."""
    _check_sect(sect)
    sign = sign_of(lon)
    held: list[str] = []
    if domicile_ruler(sign) == planet:
        held.append("domicile")
    if exaltation_ruler(sign) == planet:
        held.append("exaltation")
    if triplicity_ruler(sign, sect) == planet:
        held.append("triplicity")
    if term_ruler(lon) == planet:
        held.append("term")
    if face_ruler(lon) == planet:
        held.append("face")
    held.sort(key=_DIGNITY_ORDER.index)
    detr = is_detriment(planet, sign)
    fall = is_fall(planet, sign)
    score = sum(DIGNITY_POINTS[d] for d in held)
    peregrine = not held and not detr and not fall
    return DignityState(planet, sign, held, detr, fall, peregrine, score)


@dataclass
class AlmutenResult:
    winner: str
    scores: dict          # planet -> total dignity points over the degree
    lon: float
    sect: str


def almuten(lon: float, sect: str) -> AlmutenResult:
    """The almuten (lord) of a degree: planet with the highest summed dignity
    points over that degree across the five essential dignities.

    Ties are broken deterministically — higher single dignity first, then
    Chaldean order — not by any one historical author's rule (those vary).
    """
    _check_sect(sect)
    sign = sign_of(lon)
    scores: dict[str, int] = {}
    best_single: dict[str, int] = {}

    def _add(planet, points):
        if planet is None:
            return
        scores[planet] = scores.get(planet, 0) + points
        best_single[planet] = max(best_single.get(planet, 0), points)

    _add(domicile_ruler(sign), DIGNITY_POINTS["domicile"])
    _add(exaltation_ruler(sign), DIGNITY_POINTS["exaltation"])
    _add(triplicity_ruler(sign, sect), DIGNITY_POINTS["triplicity"])
    _add(term_ruler(lon), DIGNITY_POINTS["term"])
    _add(face_ruler(lon), DIGNITY_POINTS["face"])

    winner = max(
        scores,
        key=lambda p: (scores[p], best_single[p], -_CHALDEAN_ORDER.index(p)),
    )
    return AlmutenResult(winner, scores, lon, sect)


# ---------------------------------------------------------------------------
# Lots (Arabic Parts)
# ---------------------------------------------------------------------------
# Fortune and Spirit are the two primary lots and reverse by sect: the night
# formula of one is the day formula of the other. Fortune marks the body /
# fortune, Spirit the mind / action.

def lot_value(asc: float, a: float, b: float, sect: str) -> float:
    """The general Hellenistic lot rule — by day ``Asc + A − B``, by night the
    reflection ``Asc + B − A``. Every Hermetic lot is an instance of it."""
    if _check_sect(sect) == DIURNAL:
        return (asc + a - b) % 360.0
    return (asc + b - a) % 360.0


def lot_of_fortune(asc: float, sun: float, moon: float, sect: str) -> float:
    """Lot of Fortune: Asc + Moon − Sun by day, reversed by night."""
    return lot_value(asc, moon, sun, sect)


def lot_of_spirit(asc: float, sun: float, moon: float, sect: str) -> float:
    """Lot of Spirit: Asc + Sun − Moon by day, reversed by night (Fortune's reverse)."""
    return lot_value(asc, sun, moon, sect)


# The seven Hermetic lots (Paulus Alexandrinus): name -> (A term, B term), where
# a term is a planet name or a previously-computed lot ("Fortune"/"Spirit").
# day = Asc + A − B, night swaps. Each lot corresponds to one planet
# (Fortune↔Moon, Spirit↔Sun, Eros↔Venus, Necessity↔Mercury, Courage↔Mars,
# Victory↔Jupiter, Nemesis↔Saturn); Eros & Victory are Spirit-derived,
# Necessity/Courage/Nemesis Fortune-derived. Sources: the explicit day/night
# formulas for Eros/Necessity/Courage/Victory at
# twowander.com/blog/what-are-hermetic-lots-arabic-parts, cross-checked against
# the lot↔planet correspondence and the derived-family pattern (astrology-api.io
# + search corroboration). NB Nemesis is Saturn-based (Asc + Fortune − Saturn);
# a stray source printing "− Spirit" is a typo, inconsistent with Nemesis↔Saturn.
HERMETIC_LOTS = {
    "Fortune":   ("Moon", "Sun"),
    "Spirit":    ("Sun", "Moon"),
    "Eros":      ("Venus", "Spirit"),
    "Necessity": ("Fortune", "Mercury"),
    "Courage":   ("Fortune", "Mars"),
    "Victory":   ("Jupiter", "Spirit"),
    "Nemesis":   ("Fortune", "Saturn"),
}

# Computation / display order — Fortune and Spirit first, since the derived lots
# reference them.
LOT_ORDER = ("Fortune", "Spirit", "Eros", "Necessity", "Courage", "Victory", "Nemesis")


def lots(chart) -> dict:
    """All seven Hermetic lots for a computed chart (uses the chart's own sect).

    Raises cleanly if the chart lacks Sun/Ascendant (sect is then undefined).
    """
    sect = chart_sect(chart)
    asc = next(a for a in chart.angles if a.name == "Ascendant").longitude
    plon = {p.name: p.longitude for p in chart.planets}
    result: dict[str, float] = {}

    def resolve(term: str) -> float:
        # A term is either a planet longitude or an already-computed lot.
        return result[term] if term in result else plon[term]

    for name in LOT_ORDER:
        a_term, b_term = HERMETIC_LOTS[name]
        result[name] = lot_value(asc, resolve(a_term), resolve(b_term), sect)
    return result


# ---------------------------------------------------------------------------
# Profections (annual / monthly time-lords)
# ---------------------------------------------------------------------------
# Annual profection advances the chart one whole sign per completed year of life
# from the natal Ascendant — age 0 is the 1st house (the Ascendant sign) — on a
# 12-year cycle; the lord of the year is the domicile ruler of the profected
# sign. Monthly profection advances one sign per 1/12 of the year from the annual
# sign. (Dorothean/Valens convention.)

@dataclass
class Profection:
    age: int
    profected_sign: str
    profected_house: int   # 1..12
    lord_of_year: str


def annual_profection(asc_lon: float, age: int) -> Profection:
    if age < 0:
        raise ValueError(f"age must be >= 0, got {age}")
    asc_idx = SIGNS.index(sign_of(asc_lon))
    sign = SIGNS[(asc_idx + age) % 12]
    return Profection(age, sign, (age % 12) + 1, domicile_ruler(sign))


def monthly_profected_sign(asc_lon: float, age: int, month: int) -> str:
    """Profected sign for *month* (0-based) within the profection year — month 0
    is the annual profected sign, then one sign per 1/12 of the year."""
    if age < 0:
        raise ValueError(f"age must be >= 0, got {age}")
    asc_idx = SIGNS.index(sign_of(asc_lon))
    return SIGNS[(asc_idx + age + month) % 12]


def years_completed(birth_iso: str, target_iso: str) -> int:
    """Completed years (birthdays elapsed) between two ISO dates — the age that
    drives annual profection. Raises if *target* precedes birth."""
    b = date.fromisoformat(birth_iso)
    t = date.fromisoformat(target_iso)
    if t < b:
        raise ValueError(f"target date {target_iso} precedes birth {birth_iso}")
    years = t.year - b.year
    if (t.month, t.day) < (b.month, b.day):
        years -= 1
    return years


@dataclass
class ProfectionReport:
    profection: Profection
    lord_sign: str             # the lord of the year's natal sign
    lord_house: Optional[int]  # its natal house (None if no houses)
    lord_longitude: float
    lord_dignities: DignityState

    def to_dict(self) -> dict:
        return {
            "kind": "profection",
            "age": self.profection.age,
            "profected_sign": self.profection.profected_sign,
            "profected_house": self.profection.profected_house,
            "lord_of_year": self.profection.lord_of_year,
            "lord_sign": self.lord_sign,
            "lord_house": self.lord_house,
            "lord_longitude": self.lord_longitude,
            "lord_dignities": asdict(self.lord_dignities),
        }


def profection_report(natal, age: int) -> ProfectionReport:
    """Annual profection for *age*, plus the natal condition of the lord of the
    year — the interpretively load-bearing part (its sign, house, and dignity)."""
    sect = chart_sect(natal)
    asc = next(a for a in natal.angles if a.name == "Ascendant").longitude
    prof = annual_profection(asc, age)
    pe = next(p for p in natal.planets if p.name == prof.lord_of_year)
    dign = dignities_of(prof.lord_of_year, pe.longitude, sect)
    return ProfectionReport(prof, dign.sign, pe.house, pe.longitude, dign)


# ---------------------------------------------------------------------------
# Assembly — a full medieval chart layered on the natal computation
# ---------------------------------------------------------------------------
# The seven classical planets are the only bodies with essential dignity; the
# modern planets, asteroids, and nodes carried in the natal chart have no
# rulerships, so dignity analysis is restricted to these seven.
CLASSICAL_PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")

# The medieval default house system (spec §1); Swiss Eph code 'B'.
DEFAULT_HOUSE_SYSTEM = "alcabitius"


@dataclass
class MedievalChart:
    natal: object              # chart.NatalChart (positions, houses, aspects)
    sect: str
    sect_light: str
    benefic_of_sect: str
    malefic_of_sect: str
    contrary_malefic: str
    dignities: list            # list[DignityState], the seven classical planets
    almuten_asc: AlmutenResult  # almuten (lord) of the Ascendant degree
    lots: dict                 # the seven Hermetic lots {name: longitude}
    antiscia: list             # list[Antiscion], the seven classical planets
    antiscia_contacts: list    # list[AntisciaContact] within orb
    mutual_receptions: list    # list[MutualReception] by domicile/exaltation

    def to_dict(self) -> dict:
        return {
            "kind": "medieval",
            "natal": self.natal.to_dict(),
            "sect": self.sect,
            "sect_light": self.sect_light,
            "benefic_of_sect": self.benefic_of_sect,
            "malefic_of_sect": self.malefic_of_sect,
            "contrary_malefic": self.contrary_malefic,
            "dignities": [asdict(d) for d in self.dignities],
            "almuten_asc": asdict(self.almuten_asc),
            "lots": self.lots,
            "antiscia": [asdict(a) for a in self.antiscia],
            "antiscia_contacts": [asdict(c) for c in self.antiscia_contacts],
            "mutual_receptions": [asdict(m) for m in self.mutual_receptions],
        }


def compute_medieval(person: dict, house_system: str = DEFAULT_HOUSE_SYSTEM) -> MedievalChart:
    """Compute the medieval layer (sect, dignities, lots, almuten) on top of the
    natal chart. Defaults to Alcabitius houses (spec §1).

    Pure computation — no interpretation prose or citations (those depend on the
    verified corpus, a separate sub-project; see docs/research/biblio.md).
    """
    # Lazy import of the natal engine. chart.py is a top-level script in
    # scripts/: it resolves as `chart` when scripts/ is on sys.path (CLI + test
    # harness) and as `..chart` under package invocation (scripts.lib.medieval).
    # Handle both, per the dual-invocation contract used across the package.
    try:
        from .. import chart as chart_mod  # type: ignore[no-redef]
    except (ImportError, ValueError):
        import chart as chart_mod  # type: ignore[import-not-found,no-redef]

    natal = chart_mod.compute_natal(person, house_system=house_system)
    sect = chart_sect(natal)
    lon_by_name = natal.index_by_name()
    dignities = [
        dignities_of(name, lon_by_name[name], sect)
        for name in CLASSICAL_PLANETS
        if name in lon_by_name
    ]
    asc = next(a for a in natal.angles if a.name == "Ascendant")
    return MedievalChart(
        natal=natal,
        sect=sect,
        sect_light=sect_light(sect),
        benefic_of_sect=benefic_of_sect(sect),
        malefic_of_sect=malefic_of_sect(sect),
        contrary_malefic=contrary_malefic(sect),
        dignities=dignities,
        almuten_asc=almuten(asc.longitude, sect),
        lots=lots(natal),
        antiscia=antiscia(natal),
        antiscia_contacts=antiscia_contacts(natal),
        mutual_receptions=mutual_receptions(natal),
    )


# ---------------------------------------------------------------------------
# Antiscia / contra-antiscia
# ---------------------------------------------------------------------------
# Antiscia mirror a degree across the solstitial (0° Cancer–0° Capricorn) axis:
# antiscion(λ) = (180 − λ) mod 360 — equal distance from the Cancer/Capricorn
# solstice points. Contra-antiscia mirror across the equinoctial (0° Aries–0°
# Libra) axis: contra(λ) = (−λ) mod 360, i.e. the antiscion reflected by 180°.

def antiscion(lon: float) -> float:
    return (180.0 - lon) % 360.0


def contra_antiscion(lon: float) -> float:
    return (-lon) % 360.0


@dataclass
class Antiscion:
    planet: str
    longitude: float
    antiscion: float
    contra_antiscion: float


@dataclass
class AntisciaContact:
    a: str       # the body whose antiscion/contra-antiscion is contacted
    b: str       # the body sitting on it
    kind: str    # "antiscion" | "contra-antiscion"
    orb: float


def antiscia(chart) -> list:
    """Antiscion and contra-antiscion of each classical planet in *chart*."""
    plon = {p.name: p.longitude for p in chart.planets}
    return [
        Antiscion(name, plon[name], antiscion(plon[name]), contra_antiscion(plon[name]))
        for name in CLASSICAL_PLANETS if name in plon
    ]


def antiscia_contacts_from_positions(positions: dict, orb: float = 1.0) -> list:
    """Contacts where one body sits on another's antiscion or contra-antiscion.

    Antiscion is an involution, so each contact is reported once per unordered
    pair (body *b* falling on body *a*'s antiscion / contra-antiscion).
    """
    names = list(positions)
    out: list = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            d_anti = formatting.shorter_arc_separation(antiscion(positions[a]), positions[b])
            if d_anti <= orb:
                out.append(AntisciaContact(a, b, "antiscion", round(d_anti, 4)))
            d_contra = formatting.shorter_arc_separation(contra_antiscion(positions[a]), positions[b])
            if d_contra <= orb:
                out.append(AntisciaContact(a, b, "contra-antiscion", round(d_contra, 4)))
    return out


def antiscia_contacts(chart, orb: float = 1.0) -> list:
    plon = {p.name: p.longitude for p in chart.planets if p.name in CLASSICAL_PLANETS}
    return antiscia_contacts_from_positions(plon, orb)


# ---------------------------------------------------------------------------
# Reception
# ---------------------------------------------------------------------------
# A planet "receives" another that occupies a place it rules. Mutual reception is
# when two planets each sit in a sign the other rules. The classically weighty
# form is by domicile or exaltation (the default); term/face receptions are
# common and minor, so they are opt-in via *by*.
RECEPTION_DEFAULT = ("domicile", "exaltation")


@dataclass
class MutualReception:
    a: str
    b: str
    a_receives_b: list   # dignities by which a rules b's place
    b_receives_a: list   # dignities by which b rules a's place


def _receives(receiver: str, occupant_lon: float, sect: str, by) -> list:
    """Dignity types (restricted to *by*) by which *receiver* rules *occupant_lon*."""
    return [d for d in dignities_of(receiver, occupant_lon, sect).dignities if d in by]


def mutual_receptions_from_positions(positions: dict, sect: str,
                                     by=RECEPTION_DEFAULT) -> list:
    """Mutual receptions among *positions* (name -> longitude): each unordered
    pair where both planets rule each other's place by a dignity type in *by*."""
    names = list(positions)
    out: list = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            a_recv_b = _receives(a, positions[b], sect, by)
            b_recv_a = _receives(b, positions[a], sect, by)
            if a_recv_b and b_recv_a:
                out.append(MutualReception(a, b, a_recv_b, b_recv_a))
    return out


def mutual_receptions(chart, by=RECEPTION_DEFAULT) -> list:
    sect = chart_sect(chart)
    plon = {p.name: p.longitude for p in chart.planets if p.name in CLASSICAL_PLANETS}
    return mutual_receptions_from_positions(plon, sect, by)
