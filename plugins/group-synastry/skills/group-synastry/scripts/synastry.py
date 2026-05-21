"""Pairwise synastry: cross-aspects + house overlays both directions.

CLI:
    synastry.py <person_a> <person_b> [--house-system placidus] [--json]
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
    from lib import ephem, formatting  # type: ignore[import-not-found]
    import db, chart as chart_mod  # type: ignore[import-not-found]
else:
    from .lib import ephem, formatting
    from . import db
    from . import chart as chart_mod


# Synastry contacts always include these per spec D6.
SYNASTRY_BODIES = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto",
    "Chiron", "Lilith", "Ceres", "Eris", "True Node",
    "Ascendant", "Midheaven",
)


@dataclass
class CrossAspect:
    a_owner: str
    a_body: str
    b_owner: str
    b_body: str
    aspect: str
    orb_deg: float
    a_lon: float
    b_lon: float


@dataclass
class HouseOverlayEntry:
    visitor: str          # whose planet
    body: str
    house: int            # which house in the host's chart
    longitude: float


@dataclass
class SynastryReport:
    person_a: str
    person_b: str
    chart_a: dict
    chart_b: dict
    aspects: list[CrossAspect] = field(default_factory=list)
    overlays_a_in_b: list[HouseOverlayEntry] = field(default_factory=list)
    overlays_b_in_a: list[HouseOverlayEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _index_chart(chart: chart_mod.NatalChart) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in chart.planets:
        out[p.name] = p.longitude
    for a in chart.angles:
        out[a.name] = a.longitude
    return out


def compute_synastry(person_a: dict, person_b: dict, house_system: str = "placidus") -> SynastryReport:
    chart_a = chart_mod.compute_natal(person_a, house_system=house_system)
    chart_b = chart_mod.compute_natal(person_b, house_system=house_system)
    a_idx = _index_chart(chart_a)
    b_idx = _index_chart(chart_b)

    aspects: list[CrossAspect] = []
    for nm_a in SYNASTRY_BODIES:
        if nm_a not in a_idx:
            continue
        for nm_b in SYNASTRY_BODIES:
            if nm_b not in b_idx:
                continue
            sep = abs(a_idx[nm_a] - b_idx[nm_b]) % 360.0
            if sep > 180.0:
                sep = 360.0 - sep
            classified = formatting.aspect_from_separation(sep)
            if classified is None:
                continue
            name, _exact, orb = classified
            aspects.append(CrossAspect(
                a_owner=person_a.get("display_name", person_a["id"]),
                a_body=nm_a,
                b_owner=person_b.get("display_name", person_b["id"]),
                b_body=nm_b,
                aspect=name, orb_deg=orb,
                a_lon=a_idx[nm_a], b_lon=b_idx[nm_b],
            ))
    aspects.sort(key=lambda x: x.orb_deg)

    overlays_a_in_b = _overlay(chart_a, chart_b)
    overlays_b_in_a = _overlay(chart_b, chart_a)

    return SynastryReport(
        person_a=person_a.get("display_name", person_a["id"]),
        person_b=person_b.get("display_name", person_b["id"]),
        chart_a=_natal_to_dict(chart_a),
        chart_b=_natal_to_dict(chart_b),
        aspects=aspects,
        overlays_a_in_b=overlays_a_in_b,
        overlays_b_in_a=overlays_b_in_a,
    )


def _natal_to_dict(c: chart_mod.NatalChart) -> dict:
    return {
        "person_id": c.person_id,
        "display_name": c.display_name,
        "ut_iso": c.ut_iso,
        "house_system": c.house_system,
        "planets": [asdict(p) for p in c.planets],
        "angles": [asdict(a) for a in c.angles],
    }


def _overlay(visitor: chart_mod.NatalChart, host: chart_mod.NatalChart) -> list[HouseOverlayEntry]:
    if not host.house_cusps:
        return []
    cusps = tuple(host.house_cusps)
    out: list[HouseOverlayEntry] = []
    for p in visitor.planets:
        h = ephem.assign_house(p.longitude, cusps)
        out.append(HouseOverlayEntry(visitor.display_name, p.name, h, p.longitude))
    return out


# ---- CLI -----------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Synastry between two people.")
    parser.add_argument("ident_a")
    parser.add_argument("ident_b")
    parser.add_argument("--house-system", default="placidus")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--interpretation",
        help="Path to interpretation source (.json or .md sidecar). Appended "
             "after the chart data when rendering markdown. Ignored with --json.",
    )
    args = parser.parse_args(argv)

    data = db.load()
    a = db.find(data, args.ident_a)
    b = db.find(data, args.ident_b)
    missing = [x for x, y in (("a", a), ("b", b)) if y is None]
    if missing:
        labels = {"a": args.ident_a, "b": args.ident_b}
        for m in missing:
            print(f"Person not found: {labels[m]}", file=sys.stderr)
        return 1
    report = compute_synastry(a, b, house_system=args.house_system)
    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False, default=str))
        return 0
    if __package__ in (None, ""):
        from render_md import render_synastry, render_interpretation  # type: ignore[import-not-found]
        import render_docx as _rdocx  # type: ignore[import-not-found]
    else:
        from .render_md import render_synastry, render_interpretation
        from . import render_docx as _rdocx
    interpretation = None
    if args.interpretation:
        try:
            interpretation = _rdocx.parse_interpretation_file(Path(args.interpretation))
        except (OSError, json.JSONDecodeError, _rdocx.RenderError) as exc:
            print(f"Error reading --interpretation {args.interpretation}: {exc}", file=sys.stderr)
            return 2
    print(render_synastry(report) + render_interpretation(interpretation))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
