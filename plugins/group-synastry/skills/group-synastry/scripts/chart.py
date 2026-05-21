"""Western tropical natal chart computation.

CLI:
    chart.py natal <person_id> [--house-system placidus] [--json]

Returns a structured chart dict. When --json is set, prints JSON to stdout;
otherwise routes through render_md for a human-readable Markdown chart.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import ephem, formatting, settings  # type: ignore[import-not-found]
    from lib.tz import to_julian_day_ut  # type: ignore[import-not-found]
    import db  # type: ignore[import-not-found]
else:
    from .lib import ephem, formatting, settings
    from .lib.tz import to_julian_day_ut
    from . import db


# Bodies always reported in a Western tropical natal chart, in display order.
NATAL_BODIES = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto",
    "Chiron", "Ceres", "Eris", "Lilith",
    "True Node",
)


@dataclass
class PlanetEntry:
    name: str
    longitude: float
    sign: str
    degree: int
    minute: int
    second: int
    retrograde: bool
    speed: float
    house: Optional[int]
    source: str             # "swisseph" | "keplerian"

    @classmethod
    def from_position(cls, pos: ephem.BodyPosition, house: Optional[int]) -> "PlanetEntry":
        p = formatting.split_longitude(pos.longitude)
        return cls(
            name=pos.name,
            longitude=pos.longitude,
            sign=p.sign, degree=p.degree, minute=p.minute, second=p.second,
            retrograde=pos.retrograde, speed=pos.speed,
            house=house, source=pos.source,
        )


@dataclass
class AngleEntry:
    name: str
    longitude: float
    sign: str
    degree: int
    minute: int
    second: int

    @classmethod
    def from_longitude(cls, name: str, lon: float) -> "AngleEntry":
        p = formatting.split_longitude(lon)
        return cls(name, lon, p.sign, p.degree, p.minute, p.second)


@dataclass
class AspectEntry:
    a: str
    b: str
    aspect: str
    orb_deg: float
    applying: Optional[bool]  # None when speeds aren't known


@dataclass
class NatalChart:
    person_id: str
    display_name: str
    birth: dict
    julian_day_ut: float
    ut_iso: str
    house_system: str
    zodiac: str = "tropical"
    planets: list[PlanetEntry] = field(default_factory=list)
    angles: list[AngleEntry] = field(default_factory=list)
    house_cusps: list[float] = field(default_factory=list)
    aspects: list[AspectEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def compute_natal(person: dict, house_system: str = "placidus") -> NatalChart:
    birth = person["birth"]
    conv = to_julian_day_ut(birth["date"], birth["time"], birth["tz"])
    notes: list[str] = []

    # Bodies
    planets: list[PlanetEntry] = []
    cusps_tuple: tuple = ()
    if birth.get("time_accuracy") not in ("unknown",):
        houses = ephem.calc_houses(conv.julian_day_ut, birth["lat"], birth["lon"], house_system)
        cusps_tuple = houses.cusps
        angles = [
            AngleEntry.from_longitude("Ascendant", houses.ascendant),
            AngleEntry.from_longitude("Midheaven", houses.midheaven),
            AngleEntry.from_longitude("Descendant", houses.descendant),
            AngleEntry.from_longitude("IC", houses.ic),
            AngleEntry.from_longitude("Vertex", houses.vertex),
        ]
        cusps_list = list(houses.cusps)
    else:
        notes.append(
            "Birth time is marked as unknown — Ascendant, MC, IC, Descendant, "
            "Vertex, and house cusps are omitted. Sign positions for the "
            "luminaries and planets remain valid."
        )
        angles = []
        cusps_list = []

    fallback_bodies: list[str] = []
    for name in NATAL_BODIES:
        pos = ephem.calc_body(conv.julian_day_ut, name)
        house = ephem.assign_house(pos.longitude, cusps_tuple) if cusps_tuple else None
        planets.append(PlanetEntry.from_position(pos, house))
        if pos.source == "keplerian":
            fallback_bodies.append(name)

    # Synthetic South Node (always derived from True Node)
    tn = next((p for p in planets if p.name == "True Node"), None)
    if tn is not None:
        sn_lon = ephem.south_node(tn.longitude)
        sn_pos = ephem.BodyPosition("South Node", sn_lon, -tn.speed, tn.source)
        house = ephem.assign_house(sn_lon, cusps_tuple) if cusps_tuple else None
        planets.append(PlanetEntry.from_position(sn_pos, house))

    if fallback_bodies:
        notes.append(
            "Bodies computed via bundled Keplerian elements (no Swiss Ephemeris "
            f"asteroid file available): {', '.join(fallback_bodies)}. "
            "Accuracy is ~arcminutes for Ceres/Eris and degree-scale for Chiron."
        )

    # Aspects between bodies (and to angles when angles available)
    aspect_targets = list(planets)
    angle_pseudo: list[PlanetEntry] = []
    for a in angles:
        if a.name in ("Ascendant", "Midheaven"):
            angle_pseudo.append(
                PlanetEntry(a.name, a.longitude, a.sign, a.degree, a.minute, a.second,
                            False, 0.0, None, "swisseph")
            )
    aspect_pool = aspect_targets + angle_pseudo
    aspects = _compute_aspects(aspect_pool)

    chart = NatalChart(
        person_id=person["id"],
        display_name=person.get("display_name", person["id"]),
        birth=birth,
        julian_day_ut=conv.julian_day_ut,
        ut_iso=conv.ut_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
        house_system=house_system if cusps_list else "n/a",
        planets=planets,
        angles=angles,
        house_cusps=cusps_list,
        aspects=aspects,
        notes=notes,
    )
    return chart


_NODE_PAIR = {"True Node", "South Node"}


def _compute_aspects(bodies: list[PlanetEntry]) -> list[AspectEntry]:
    out: list[AspectEntry] = []
    for i, a in enumerate(bodies):
        for b in bodies[i + 1:]:
            # The North/South Node opposition is tautological; skip it.
            if {a.name, b.name} == _NODE_PAIR:
                continue
            sep = abs(a.longitude - b.longitude) % 360.0
            if sep > 180.0:
                sep = 360.0 - sep
            classified = formatting.aspect_from_separation(sep)
            if classified is None:
                continue
            name, exact, orb = classified
            applying: Optional[bool] = None
            if a.speed != 0.0 or b.speed != 0.0:
                # Separation rate; negative means orb shrinking → applying.
                ds = (a.speed - b.speed)
                applying = ds < 0
            out.append(AspectEntry(a.name, b.name, name, orb, applying))
    out.sort(key=lambda x: x.orb_deg)
    return out


# ---- CLI -----------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute natal charts.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_natal = sub.add_parser("natal")
    p_natal.add_argument("ident", help="person id or display_name")
    p_natal.add_argument(
        "--house-system",
        default=None,
        help="house system (default: settings.default_house_system, else placidus)",
    )
    p_natal.add_argument("--json", action="store_true",
                         help="print chart as JSON instead of Markdown")
    p_natal.add_argument(
        "--interpretation",
        help="Path to interpretation source (.json or .md sidecar). Appended "
             "after the chart data when rendering markdown. Ignored with --json.",
    )
    args = parser.parse_args(argv)

    house_system = args.house_system or settings.default_house_system()

    data = db.load()
    person = db.find(data, args.ident)
    if not person:
        print(f"Person not found: {args.ident}", file=sys.stderr)
        return 1
    chart = compute_natal(person, house_system=house_system)
    if args.json:
        print(json.dumps(chart.to_dict(), indent=2, ensure_ascii=False, default=str))
        return 0
    # Markdown rendering
    if __package__ in (None, ""):
        from render_md import render_natal, render_interpretation  # type: ignore[import-not-found]
        import render_docx as _rdocx  # type: ignore[import-not-found]
    else:
        from .render_md import render_natal, render_interpretation
        from . import render_docx as _rdocx
    interpretation = None
    if args.interpretation:
        try:
            interpretation = _rdocx.parse_interpretation_file(Path(args.interpretation))
        except (OSError, json.JSONDecodeError, _rdocx.RenderError) as exc:
            print(f"Error reading --interpretation {args.interpretation}: {exc}", file=sys.stderr)
            return 2
    print(render_natal(chart) + render_interpretation(interpretation))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
