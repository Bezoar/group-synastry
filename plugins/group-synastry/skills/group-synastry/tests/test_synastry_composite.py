"""Synastry & composite reference tests for Alex × Jordan (fictional subjects)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import synastry as synastry_mod
import composite as composite_mod


FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


def _find_aspect(report: synastry_mod.SynastryReport, body_a: str, body_b: str, kind: str):
    for asp in report.aspects:
        if asp.aspect == kind and {(asp.a_body, asp.b_body)} == {(body_a, body_b)}:
            return asp
    for asp in report.aspects:
        if asp.aspect == kind and (asp.a_body, asp.b_body) in {(body_a, body_b), (body_b, body_a)}:
            return asp
    return None


def test_synastry_sun_trine_sun():
    """Alex Sun (Gemini) trine Jordan Sun (Aquarius) — air-sign trine ~4°."""
    report = synastry_mod.compute_synastry(PEOPLE["alex"], PEOPLE["jordan"])
    asp = _find_aspect(report, "Sun", "Sun", "trine")
    assert asp is not None, "Sun-trine-Sun missing"
    assert 3.5 < asp.orb_deg < 4.5, f"orb {asp.orb_deg}"


def test_synastry_venus_trine_sun_tight():
    """Alex Venus trine Jordan Sun — the tightest cross-aspect (~0°02')."""
    report = synastry_mod.compute_synastry(PEOPLE["alex"], PEOPLE["jordan"])
    # Alex's Venus on the A-side, Jordan's Sun on the B-side.
    found = next(
        (a for a in report.aspects
         if a.a_body == "Venus" and a.b_body == "Sun" and a.aspect == "trine"),
        None,
    )
    assert found is not None, "Alex-Venus trine Jordan-Sun missing"
    assert found.orb_deg < 0.5, f"expected tight orb (<0°30'); got {found.orb_deg}°"


def test_synastry_overlays_both_directions():
    report = synastry_mod.compute_synastry(PEOPLE["alex"], PEOPLE["jordan"])
    assert report.overlays_a_in_b, "Alex-in-Jordan overlays missing"
    assert report.overlays_b_in_a, "Jordan-in-Alex overlays missing"


def test_synastry_d6_bodies_present():
    """Per spec D6: synastry must include Chiron, Eris, Lilith, Ceres."""
    report = synastry_mod.compute_synastry(PEOPLE["alex"], PEOPLE["jordan"])
    seen = {a.a_body for a in report.aspects} | {a.b_body for a in report.aspects}
    for required in ("Chiron", "Eris", "Lilith", "Ceres"):
        assert required in seen, f"D6 body {required} missing from synastry contacts"


def test_midpoint_composite_reference():
    """Reference composite Sun ≈ 22° Aries 39', Moon ≈ 2° Libra 38' (shorter-arc
    midpoints per spec §16)."""
    comp = composite_mod.midpoint_composite(PEOPLE["alex"], PEOPLE["jordan"])
    by = {p.name: (p.sign, p.degree, p.minute) for p in comp.points}
    assert by["Sun"][0] == "Aries"
    sun_total = by["Sun"][1] * 60 + by["Sun"][2]
    assert abs(sun_total - (22 * 60 + 39)) <= 5, by["Sun"]
    assert by["Moon"][0] == "Libra"
    moon_total = by["Moon"][1] * 60 + by["Moon"][2]
    assert abs(moon_total - (2 * 60 + 38)) <= 5, by["Moon"]


def test_composite_saturn_ceres_tight_conjunction():
    """Tightest inter-body composite aspect involving an asteroid.

    With seas_18.se1 bundled and Swiss Eph used as best-source, composite Saturn
    (14° Capricorn 59') and composite Ceres (14° Capricorn 51') form a
    conjunction at ~8 arcmin. A Ceres position from the Keplerian fallback would
    not place this contact correctly.
    """
    comp = composite_mod.midpoint_composite(PEOPLE["alex"], PEOPLE["jordan"])
    asps = [a for a in comp.aspects
            if {a.a, a.b} == {"Saturn", "Ceres"}
            and a.aspect == "conjunction"]
    assert asps, "Saturn-Ceres conjunction missing from composite"
    assert asps[0].orb_deg < 0.2, f"orb too wide: {asps[0].orb_deg}"


def test_davison_moment():
    comp = composite_mod.davison(PEOPLE["alex"], PEOPLE["jordan"])
    assert comp.moment is not None
    assert comp.moment["ut_datetime"].startswith("1989-10-13"), comp.moment
    # Reference Davison location: 41.14°N, 96.45°W ± 0.5°
    assert abs(comp.moment["lat"] - 41.14) < 0.5, comp.moment["lat"]
    assert abs(comp.moment["lon"] - (-96.45)) < 0.5, comp.moment["lon"]


def test_davison_sun():
    comp = composite_mod.davison(PEOPLE["alex"], PEOPLE["jordan"])
    sun = next(p for p in comp.points if p.name == "Sun")
    assert sun.sign == "Libra"
    total = sun.degree * 60 + sun.minute
    # Reference: 19° Libra 52' ± 6'
    assert abs(total - (19 * 60 + 52)) <= 6, (sun.sign, sun.degree, sun.minute)
