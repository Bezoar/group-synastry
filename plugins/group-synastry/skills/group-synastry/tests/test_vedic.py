"""Tests for the Vedic (sidereal) computation layer (lib/vedic).

Sidereal positions use the Lahiri ayanamsa by default; sidereal longitude is the
canonical Vedic definition ``tropical − ayanamsa`` (cross-checked against
swisseph's native sidereal mode). Nakshatra names + Vimshottari lords verified
(see lib/vedic for the source). Reference placements come from the public fixture.

Vimshottari dasha *timeline* and the Navamsa (D9) divisional chart are the
deferred heavy pieces (breadth-first foundation first).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import swisseph as swe

import chart as chart_mod  # via conftest path injection
from lib import vedic

FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


# ---------------------------------------------------------------------------
# Ayanamsa + sidereal
# ---------------------------------------------------------------------------

def test_lahiri_ayanamsa_is_about_24_degrees_for_modern_dates():
    assert 23.5 < vedic.ayanamsa(2451544.5) < 24.2   # 2000-01-01


def test_unknown_ayanamsa_raises():
    with pytest.raises(ValueError):
        vedic.ayanamsa(2451544.5, mode="bogus")


def test_to_sidereal_matches_swisseph_native_sidereal_within_tolerance():
    jd = 2447328.0556  # Alex (UT)
    trop = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0][0]
    sid_native = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
    got = vedic.to_sidereal(trop, jd)
    # signed shorter-arc difference < 0.02°
    diff = (got - sid_native + 180.0) % 360.0 - 180.0
    assert abs(diff) < 0.02


# ---------------------------------------------------------------------------
# Nakshatras
# ---------------------------------------------------------------------------

def test_nakshatra_at_zero_is_ashwini_pada_1_lord_ketu():
    n = vedic.nakshatra_of(0.0)
    assert (n.index, n.name, n.pada, n.lord) == (0, "Ashwini", 1, "Ketu")


def test_nakshatra_boundaries_and_last():
    assert vedic.nakshatra_of(13.3334).name == "Bharani"   # start of #2
    assert vedic.nakshatra_of(3.34).pada == 2              # 3°20' into Ashwini
    last = vedic.nakshatra_of(359.9)
    assert (last.index, last.name, last.lord) == (26, "Revati", "Mercury")


def test_vimshottari_lord_cycle_repeats_thrice_across_27():
    lords = [vedic.nakshatra_of(i * vedic.NAKSHATRA_SPAN + 1.0).lord for i in range(27)]
    cycle = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    assert lords == cycle * 3


def test_nakshatra_table_integrity():
    assert len(vedic.NAKSHATRAS) == 27
    assert len(set(vedic.NAKSHATRAS)) == 27
    assert len(vedic.VIMSHOTTARI_CYCLE) == 9
    assert 27 % len(vedic.VIMSHOTTARI_CYCLE) == 0
    assert abs(vedic.NAKSHATRA_SPAN - (360.0 / 27.0)) < 1e-9


# ---------------------------------------------------------------------------
# Whole-Sign rasi houses (from the sidereal Ascendant)
# ---------------------------------------------------------------------------

def test_rasi_house_counts_signs_from_the_ascendant():
    assert vedic.rasi_house(95.0, 100.0) == 1    # both Cancer
    assert vedic.rasi_house(125.0, 100.0) == 2   # Leo, next sign
    assert vedic.rasi_house(85.0, 100.0) == 12   # Gemini, previous sign -> 12th


# ---------------------------------------------------------------------------
# Assembly: compute_vedic
# ---------------------------------------------------------------------------

def test_compute_vedic_sidereal_grahas_nakshatras_and_houses():
    vc = vedic.compute_vedic(PEOPLE["alex"])
    assert vc.ayanamsa_mode == "lahiri"
    assert 23.0 < vc.ayanamsa_value < 24.5
    # The nine grahas in the traditional order (Rahu/Ketu from the nodes).
    assert [g.name for g in vc.grahas] == [
        "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"
    ]
    # Alex's Sun: tropical late Gemini → sidereal early Gemini (Lahiri).
    sun = next(g for g in vc.grahas if g.name == "Sun")
    assert sun.sign == "Gemini"
    # Janma (Moon) nakshatra, computed from the verified table + ayanamsa.
    assert vc.moon_nakshatra.name == "Ardra"
    assert vc.moon_nakshatra.pada == 3
    assert vc.moon_nakshatra.lord == "Rahu"
    # Rahu and Ketu are exactly opposite.
    rahu = next(g for g in vc.grahas if g.name == "Rahu")
    ketu = next(g for g in vc.grahas if g.name == "Ketu")
    assert abs(((rahu.sidereal_longitude - ketu.sidereal_longitude) % 360) - 180.0) < 0.01
    # Rasi houses are 1..12.
    assert all(1 <= g.rasi_house <= 12 for g in vc.grahas)


def test_vedic_to_dict_is_json_serializable():
    vc = vedic.compute_vedic(PEOPLE["alex"])
    d = vc.to_dict()
    assert d["kind"] == "vedic"
    json.dumps(d)


def test_render_vedic_has_key_sections():
    from render_md import render_vedic
    vc = vedic.compute_vedic(PEOPLE["alex"])
    md = render_vedic(vc)
    assert "Vedic" in md
    assert "Sidereal" in md
    assert "Nakshatra" in md
    assert "Rasi" in md
    assert "ayanamsa" in md.lower()
