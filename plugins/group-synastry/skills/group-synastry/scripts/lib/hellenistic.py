"""Hellenistic astrology computation layer.

Reuses the shared traditional substrate in ``lib/medieval`` (sect, lots,
triplicity rulers — the Hellenistic substrate is exactly what the medieval module
already implements) and adds the Hellenistic-specific framing: **Whole-Sign
houses** numbered from the rising sign, place categories (angular / succedent /
cadent), and the **triplicity lords of the sect light**.

Computation only — no interpretation prose or citations. **Zodiacal Releasing**
(the heavy Hellenistic-specific time-lord technique) is not built in this first
cut; it is the deferred piece, analogous to firdaria/primary-directions on the
medieval side.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

if __package__ in (None, ""):
    import medieval  # type: ignore[import-not-found]
    import formatting  # type: ignore[import-not-found]  # noqa: F401  (used by renderer/JSON callers)
else:
    from . import medieval
    from . import formatting  # noqa: F401

SIGNS = medieval.SIGNS

# Hellenistic standard house system.
DEFAULT_HOUSE_SYSTEM = "whole-sign"

_ANGULAR = {1, 4, 7, 10}
_SUCCEDENT = {2, 5, 8, 11}


def whole_sign_house(planet_lon: float, asc_lon: float) -> int:
    """Whole-sign house (1..12): the rising sign is house 1, counting forward one
    whole sign per house (degree-independent; shared whole-sign helper)."""
    return formatting.whole_sign_house(planet_lon, asc_lon)


def place_category(house: int) -> str:
    """Angular (1/4/7/10), succedent (2/5/8/11), or cadent (3/6/9/12)."""
    if house in _ANGULAR:
        return "angular"
    if house in _SUCCEDENT:
        return "succedent"
    return "cadent"


def triplicity_lords_of(sign: str, sect: str) -> list:
    """The three triplicity lords ordered by sect — the in-sect lord first, then
    the out-of-sect lord, then the participating lord (Dorothean rulers, via
    ``medieval.TRIPLICITY``). The triplicity lords of the sect light are a
    standard Hellenistic life-trajectory significator."""
    element = next(el for el, signs in medieval.ELEMENTS.items() if sign in signs)
    tri = medieval.TRIPLICITY[element]
    if sect == medieval.DIURNAL:
        return [tri["day"], tri["night"], tri["participating"]]
    if sect == medieval.NOCTURNAL:
        return [tri["night"], tri["day"], tri["participating"]]
    raise ValueError(f"sect must be {medieval.DIURNAL!r} or {medieval.NOCTURNAL!r}, got {sect!r}")


# ---------------------------------------------------------------------------
# Assembly — a Hellenistic natal chart layered on the natal computation
# ---------------------------------------------------------------------------

@dataclass
class WholeSignPlacement:
    planet: str
    sign: str
    house: int        # 1..12, whole-sign from the rising sign
    category: str     # angular | succedent | cadent
    longitude: float


@dataclass
class HellenisticChart:
    natal: object
    sect: str
    sect_light: str
    benefic_of_sect: str
    malefic_of_sect: str
    contrary_malefic: str
    whole_sign_houses: list   # list[WholeSignPlacement]
    lots: dict                # the seven Hermetic lots {name: longitude}
    lot_houses: dict          # {lot name: whole-sign house}
    triplicity_lords_of_sect_light: list

    def to_dict(self) -> dict:
        return {
            "kind": "hellenistic",
            "natal": self.natal.to_dict(),
            "sect": self.sect,
            "sect_light": self.sect_light,
            "benefic_of_sect": self.benefic_of_sect,
            "malefic_of_sect": self.malefic_of_sect,
            "contrary_malefic": self.contrary_malefic,
            "whole_sign_houses": [asdict(w) for w in self.whole_sign_houses],
            "lots": self.lots,
            "lot_houses": self.lot_houses,
            "triplicity_lords_of_sect_light": self.triplicity_lords_of_sect_light,
        }


def compute_hellenistic(person: dict, house_system: str = DEFAULT_HOUSE_SYSTEM) -> HellenisticChart:
    """Compute a Hellenistic natal chart: Whole-Sign houses + sect + lots +
    triplicity lords of the sect light, reusing ``lib/medieval`` for the shared
    substrate. Defaults to Whole-Sign houses (the Hellenistic standard).

    Computation only — no prose/citations; no Zodiacal Releasing yet.
    """
    # Lazy import of the natal engine. chart.py is a top-level script in
    # scripts/: it resolves as `chart` when scripts/ is on sys.path (CLI + test
    # harness) and as `..chart` under package invocation (scripts.lib.hellenistic).
    # Handle both, per the dual-invocation contract used across the package.
    try:
        from .. import chart as chart_mod  # type: ignore[no-redef]
    except (ImportError, ValueError):
        import chart as chart_mod  # type: ignore[import-not-found,no-redef]

    natal = chart_mod.compute_natal(person, house_system=house_system)
    sect = medieval.chart_sect(natal)
    asc = next(a for a in natal.angles if a.name == "Ascendant").longitude

    placements = []
    for p in natal.planets:
        h = whole_sign_house(p.longitude, asc)
        placements.append(
            WholeSignPlacement(p.name, medieval.sign_of(p.longitude), h, place_category(h), p.longitude)
        )

    lots = medieval.lots(natal)
    lot_houses = {name: whole_sign_house(lon, asc) for name, lon in lots.items()}

    light = medieval.sect_light(sect)
    light_lon = next(p.longitude for p in natal.planets if p.name == light)
    tri_lords = triplicity_lords_of(medieval.sign_of(light_lon), sect)

    return HellenisticChart(
        natal=natal,
        sect=sect,
        sect_light=light,
        benefic_of_sect=medieval.benefic_of_sect(sect),
        malefic_of_sect=medieval.malefic_of_sect(sect),
        contrary_malefic=medieval.contrary_malefic(sect),
        whole_sign_houses=placements,
        lots=lots,
        lot_houses=lot_houses,
        triplicity_lords_of_sect_light=tri_lords,
    )
