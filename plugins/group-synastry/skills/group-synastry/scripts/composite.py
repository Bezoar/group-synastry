"""Composite charts: midpoint and Davison.

Midpoint composite: per-pair shorter-arc midpoint of each body's longitude.
The composite Ascendant/MC are the midpoints of the natal Ascendants/MCs.

Davison: cast a real chart for the temporal and spatial midpoint between the
two birth events.

CLI:
    composite.py midpoint <a> <b> [--json]
    composite.py davison  <a> <b> [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import ephem, formatting  # type: ignore[import-not-found]
    from lib.tz import to_julian_day_ut  # type: ignore[import-not-found]
    import db, chart as chart_mod  # type: ignore[import-not-found]
else:
    from .lib import ephem, formatting
    from .lib.tz import to_julian_day_ut
    from . import db
    from . import chart as chart_mod


COMPOSITE_BODIES = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto",
    "Chiron", "Ceres", "Eris", "Lilith", "True Node",
)


@dataclass
class CompositePoint:
    name: str
    longitude: float
    sign: str
    degree: int
    minute: int
    second: int
    house: Optional[int] = None


@dataclass
class CompositeChart:
    method: str               # "midpoint" or "davison"
    person_a: str
    person_b: str
    points: list[CompositePoint] = field(default_factory=list)
    angles: list[CompositePoint] = field(default_factory=list)
    house_cusps: list[float] = field(default_factory=list)
    aspects: list[chart_mod.AspectEntry] = field(default_factory=list)
    moment: Optional[dict] = None     # only set for Davison
    notes: list[str] = field(default_factory=list)


def _make_point(name: str, lon: float, house: Optional[int] = None) -> CompositePoint:
    p = formatting.split_longitude(lon)
    return CompositePoint(name, lon, p.sign, p.degree, p.minute, p.second, house)


def midpoint_composite(person_a: dict, person_b: dict, house_system: str = "placidus") -> CompositeChart:
    chart_a = chart_mod.compute_natal(person_a, house_system=house_system)
    chart_b = chart_mod.compute_natal(person_b, house_system=house_system)
    a_idx = {p.name: p.longitude for p in chart_a.planets}
    b_idx = {p.name: p.longitude for p in chart_b.planets}

    points: list[CompositePoint] = []
    for name in COMPOSITE_BODIES:
        if name not in a_idx or name not in b_idx:
            continue
        lon = formatting.shorter_arc_midpoint(a_idx[name], b_idx[name])
        points.append(_make_point(name, lon))

    angles: list[CompositePoint] = []
    cusps_list: list[float] = []
    if chart_a.angles and chart_b.angles:
        ang_a = {a.name: a.longitude for a in chart_a.angles}
        ang_b = {a.name: a.longitude for a in chart_b.angles}
        # Composite Ascendant from midpoint of natal Ascendants; MC from MC.
        asc = formatting.shorter_arc_midpoint(ang_a["Ascendant"], ang_b["Ascendant"])
        mc = formatting.shorter_arc_midpoint(ang_a["Midheaven"], ang_b["Midheaven"])
        angles = [
            _make_point("Ascendant", asc),
            _make_point("Midheaven", mc),
            _make_point("Descendant", (asc + 180.0) % 360.0),
            _make_point("IC", (mc + 180.0) % 360.0),
        ]
        # Build approximate equal houses from composite Ascendant — the
        # midpoint composite is intrinsically a derived chart, so we don't
        # try to recompute Placidus; equal-house is the conventional choice.
        cusps_list = [(asc + 30.0 * i) % 360.0 for i in range(12)]
        cusps_tuple = tuple(cusps_list)
        for pt in points:
            pt.house = ephem.assign_house(pt.longitude, cusps_tuple)

    pseudo = [chart_mod.PlanetEntry(p.name, p.longitude, p.sign, p.degree,
                                    p.minute, p.second, False, 0.0, p.house, "composite")
              for p in points] + [
        chart_mod.PlanetEntry(a.name, a.longitude, a.sign, a.degree,
                              a.minute, a.second, False, 0.0, None, "composite")
        for a in angles if a.name in ("Ascendant", "Midheaven")
    ]
    aspects = chart_mod._compute_aspects(pseudo)

    return CompositeChart(
        method="midpoint",
        person_a=chart_a.display_name,
        person_b=chart_b.display_name,
        points=points,
        angles=angles,
        house_cusps=cusps_list,
        aspects=aspects,
    )


def _great_circle_midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Great-circle midpoint of two (lat, lon) points in degrees."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    lam1, lam2 = math.radians(lon1), math.radians(lon2)
    dlam = lam2 - lam1
    bx = math.cos(phi2) * math.cos(dlam)
    by = math.cos(phi2) * math.sin(dlam)
    phi_m = math.atan2(
        math.sin(phi1) + math.sin(phi2),
        math.sqrt((math.cos(phi1) + bx) ** 2 + by ** 2),
    )
    lam_m = lam1 + math.atan2(by, math.cos(phi1) + bx)
    return math.degrees(phi_m), ((math.degrees(lam_m) + 540.0) % 360.0) - 180.0


def davison(person_a: dict, person_b: dict, house_system: str = "placidus") -> CompositeChart:
    a, b = person_a["birth"], person_b["birth"]
    conv_a = to_julian_day_ut(a["date"], a["time"], a["tz"])
    conv_b = to_julian_day_ut(b["date"], b["time"], b["tz"])
    # Temporal midpoint (UT).
    mid_dt = conv_a.ut_datetime + (conv_b.ut_datetime - conv_a.ut_datetime) / 2
    mid_lat, mid_lon = _great_circle_midpoint(a["lat"], a["lon"], b["lat"], b["lon"])
    # Build a synthetic person and reuse compute_natal.
    synth = {
        "id": "_davison_",
        "display_name": f"Davison {person_a.get('display_name', person_a['id'])} & {person_b.get('display_name', person_b['id'])}",
        "birth": {
            "date": mid_dt.strftime("%Y-%m-%d"),
            "time": mid_dt.strftime("%H:%M"),
            "tz": "UTC",
            "lat": mid_lat, "lon": mid_lon,
            "place_label": "great-circle midpoint",
            "time_accuracy": "exact",
        },
    }
    natal = chart_mod.compute_natal(synth, house_system=house_system)
    # Convert NatalChart shape into CompositeChart.
    points = [_make_point(p.name, p.longitude, p.house) for p in natal.planets]
    angles = [_make_point(a.name, a.longitude) for a in natal.angles]
    return CompositeChart(
        method="davison",
        person_a=person_a.get("display_name", person_a["id"]),
        person_b=person_b.get("display_name", person_b["id"]),
        points=points,
        angles=angles,
        house_cusps=list(natal.house_cusps),
        aspects=natal.aspects,
        moment={
            "ut_datetime": mid_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lat": mid_lat, "lon": mid_lon,
            "julian_day_ut": natal.julian_day_ut,
        },
        notes=natal.notes,
    )


# ---- CLI -----------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Composite charts.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("midpoint", "davison"):
        s = sub.add_parser(name)
        s.add_argument("ident_a")
        s.add_argument("ident_b")
        s.add_argument("--house-system", default="placidus")
        s.add_argument("--json", action="store_true")
        s.add_argument(
            "--interpretation",
            help="Path to interpretation source (.json or .md sidecar). Appended "
                 "after the chart data when rendering markdown. Ignored with --json.",
        )
    args = parser.parse_args(argv)

    data = db.load()
    a = db.find(data, args.ident_a)
    b = db.find(data, args.ident_b)
    if not a or not b:
        for ident, p in ((args.ident_a, a), (args.ident_b, b)):
            if not p:
                print(f"Person not found: {ident}", file=sys.stderr)
        return 1
    if args.cmd == "midpoint":
        report = midpoint_composite(a, b, house_system=args.house_system)
    else:
        report = davison(a, b, house_system=args.house_system)
    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False, default=str))
        return 0
    if __package__ in (None, ""):
        from render_md import render_composite, render_interpretation  # type: ignore[import-not-found]
        import render_docx as _rdocx  # type: ignore[import-not-found]
    else:
        from .render_md import render_composite, render_interpretation
        from . import render_docx as _rdocx
    interpretation = None
    if args.interpretation:
        try:
            interpretation = _rdocx.parse_interpretation_file(Path(args.interpretation))
        except (OSError, json.JSONDecodeError, _rdocx.RenderError) as exc:
            print(f"Error reading --interpretation {args.interpretation}: {exc}", file=sys.stderr)
            return 2
    print(render_composite(report) + render_interpretation(interpretation))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
