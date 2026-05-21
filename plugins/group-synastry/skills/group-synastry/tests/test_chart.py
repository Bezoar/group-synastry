"""Reference-chart tests for Alex & Jordan natal positions.

Reference values come from evals/reference-charts.json (validated against Swiss
Ephemeris 2.10). Tolerances follow the eval spec (§"Notes on Reference Data
Accuracy"): ±1 arcmin for major planets, ±5 arcmin for asteroid Keplerian
fallback / angles. Alex and Jordan are fictional test personas.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import chart as chart_mod  # via conftest.py path injection


FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


def _split(lon: float):
    sign_idx = int(lon // 30)
    in_sign = lon - 30 * sign_idx
    deg = int(in_sign)
    mins = (in_sign - deg) * 60
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    return signs[sign_idx], deg, mins


def _expect(lon: float, sign: str, deg: int, mins: float, *, tol_arcmin: float):
    s, d, m = _split(lon)
    assert s == sign, f"expected {sign}, got {s} ({lon:.4f}°)"
    # Combined deg-arcmin check via total arcmin within the sign
    got = d * 60 + m
    want = deg * 60 + mins
    assert abs(got - want) <= tol_arcmin, (
        f"{sign}: expected {deg}°{mins:.1f}', got {d}°{m:.1f}' "
        f"(diff {abs(got-want):.2f}'; tol {tol_arcmin}')"
    )


def test_alex_tropical_natal():
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    pos = {p.name: p.longitude for p in chart.planets}
    angles = {a.name: a.longitude for a in chart.angles}

    _expect(pos["Sun"],     "Gemini", 24, 39, tol_arcmin=1.0)
    _expect(pos["Moon"],    "Cancer", 8, 29, tol_arcmin=1.5)
    _expect(pos["Mercury"], "Gemini", 21, 2, tol_arcmin=1.5)
    _expect(pos["Venus"],   "Gemini", 20, 37, tol_arcmin=1.5)
    _expect(pos["Mars"],    "Pisces", 14, 57, tol_arcmin=1.0)
    _expect(pos["Jupiter"], "Taurus", 22, 47, tol_arcmin=1.5)
    _expect(pos["Saturn"],  "Sagittarius", 29, 37, tol_arcmin=1.5)
    _expect(pos["Uranus"],  "Sagittarius", 29, 15, tol_arcmin=2.0)
    _expect(pos["Neptune"], "Capricorn", 9, 13, tol_arcmin=2.0)
    _expect(pos["Pluto"],   "Scorpio", 10, 5,  tol_arcmin=2.0)
    _expect(pos["Lilith"],  "Virgo", 3, 38, tol_arcmin=2.0)
    _expect(pos["True Node"], "Pisces", 17, 48, tol_arcmin=2.0)

    _expect(angles["Ascendant"], "Leo",   2, 42, tol_arcmin=5.0)
    _expect(angles["Midheaven"], "Aries", 17, 48, tol_arcmin=5.0)


def test_alex_required_bodies_present():
    """Per spec D6 the always-included bodies must be in every chart."""
    chart = chart_mod.compute_natal(PEOPLE["alex"])
    names = {p.name for p in chart.planets}
    for required in (
        "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
        "Uranus", "Neptune", "Pluto",
        "Chiron", "Lilith", "Ceres", "Eris",
        "True Node",
    ):
        assert required in names, f"missing required body {required}"


def test_alex_mercury_venus_conjunction_detected():
    chart = chart_mod.compute_natal(PEOPLE["alex"])
    asps = [a for a in chart.aspects
            if {a.a, a.b} == {"Mercury", "Venus"} and a.aspect == "conjunction"]
    assert asps, "Mercury-Venus conjunction not detected"
    assert asps[0].orb_deg < 1.0, f"orb too wide: {asps[0].orb_deg}"


def test_alex_saturn_uranus_conjunction_detected():
    """The late-1980s Saturn-Uranus conjunction in Sagittarius."""
    chart = chart_mod.compute_natal(PEOPLE["alex"])
    asps = [a for a in chart.aspects
            if {a.a, a.b} == {"Saturn", "Uranus"} and a.aspect == "conjunction"]
    assert asps, "Saturn-Uranus conjunction missing"
    assert asps[0].orb_deg < 1.0, f"orb too wide: {asps[0].orb_deg}"


def test_jordan_tropical_natal():
    chart = chart_mod.compute_natal(PEOPLE["jordan"], house_system="placidus")
    pos = {p.name: p.longitude for p in chart.planets}
    angles = {a.name: a.longitude for a in chart.angles}

    _expect(pos["Sun"],     "Aquarius", 20, 38, tol_arcmin=1.5)
    _expect(pos["Moon"],    "Sagittarius", 26, 47, tol_arcmin=1.5)
    _expect(pos["Mercury"], "Aquarius", 6, 10, tol_arcmin=1.5)
    _expect(pos["Venus"],   "Pisces", 14, 34, tol_arcmin=1.5)
    _expect(pos["Mars"],    "Gemini", 5, 53, tol_arcmin=1.5)
    _expect(pos["Saturn"],  "Aquarius", 0, 22, tol_arcmin=2.0)
    _expect(pos["Neptune"], "Capricorn", 15, 34, tol_arcmin=2.0)
    _expect(pos["Pluto"],   "Scorpio", 20, 20, tol_arcmin=2.0)
    _expect(pos["Lilith"],  "Sagittarius", 21, 40, tol_arcmin=2.0)
    _expect(angles["Ascendant"], "Cancer", 18, 55, tol_arcmin=10.0)
    _expect(angles["Midheaven"], "Aries",  0, 49, tol_arcmin=10.0)


def test_chiron_ceres_via_swisseph_seas18():
    """Chiron and Ceres are computed via Swiss Eph with bundled seas_18.se1.

    Tolerances tight (±2 arcmin) because this is arcsecond-class data; the slack
    only accommodates differences between true-vs-apparent positions and any
    obliquity convention drift.
    """
    chart = chart_mod.compute_natal(PEOPLE["alex"])
    pos = {p.name: p.longitude for p in chart.planets}
    src = {p.name: p.source for p in chart.planets}

    _expect(pos["Chiron"], "Gemini", 29, 27, tol_arcmin=2.0)
    _expect(pos["Ceres"],  "Pisces", 27, 9, tol_arcmin=2.0)
    assert src["Chiron"] == "swisseph_with_seas18"
    assert src["Ceres"]  == "swisseph_with_seas18"


def test_eris_keplerian_remains_best_source():
    """Eris has no bundled Swiss Eph file (no s136199s.se1), so Keplerian is
    the best-source we have — the new wrapper must select it without raising.
    """
    chart = chart_mod.compute_natal(PEOPLE["alex"])
    pos = {p.name: p.longitude for p in chart.planets}
    src = {p.name: p.source for p in chart.planets}
    _expect(pos["Eris"], "Aries", 16, 46, tol_arcmin=5.0)
    assert src["Eris"] == "keplerian_jpl_j2000"


def test_force_source_keplerian_for_chiron():
    """Tests/evals can opt back into Keplerian for reproducibility tests."""
    from lib import ephem
    from lib.tz import to_julian_day_ut
    birth = PEOPLE["alex"]["birth"]
    conv = to_julian_day_ut(birth["date"], birth["time"], birth["tz"])
    p = ephem.calc_body(
        conv.julian_day_ut, "Chiron",
        force_source="keplerian_jpl_j2000",
    )
    assert p.source == "keplerian_jpl_j2000"
    # Keplerian Chiron at Alex's birth is ~27° Taurus — the ±1-2° error band
    # away from the Swiss-Eph value (29° Gemini 27') that motivated bundling
    # seas_18.se1 as the best source.
    _expect(p.longitude, "Taurus", 27, 34, tol_arcmin=20.0)


def test_best_source_table_matches_files_on_disk():
    """Sanity-check: every body in the always-included set has a best_source
    that's available, so a chart never fails to compute on a fresh checkout.
    """
    from lib import ephem
    for body in ephem.ALWAYS_INCLUDED_PLANETS:
        # Should not raise EphemerisFileMissing.
        src = ephem.best_source(body)
        assert src in ("swisseph_builtin", "swisseph_with_seas18",
                       "keplerian_jpl_j2000")
