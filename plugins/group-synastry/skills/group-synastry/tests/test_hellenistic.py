"""Tests for the Hellenistic computation layer (lib/hellenistic).

Hellenistic reuses the shared substrate in lib/medieval (sect, lots, triplicity
rulers) and adds the Hellenistic-specific framing: Whole-Sign houses numbered
from the rising sign, and the triplicity lords of the sect light. Reference
placements for Alex/Jordan come from the public test fixture.

Zodiacal Releasing (the one heavy Hellenistic-specific technique) is deliberately
out of this first cut — see the plan.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import chart as chart_mod  # via conftest path injection
from lib import hellenistic
from lib import medieval

FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


def _lon(sign: str, deg: float) -> float:
    return medieval.SIGNS.index(sign) * 30.0 + deg


# ---------------------------------------------------------------------------
# Whole-Sign houses
# ---------------------------------------------------------------------------

def test_whole_sign_house_counts_signs_from_the_ascendant():
    asc = _lon("Leo", 2.0)
    assert hellenistic.whole_sign_house(_lon("Leo", 28.0), asc) == 1   # rising sign
    assert hellenistic.whole_sign_house(_lon("Virgo", 1.0), asc) == 2
    assert hellenistic.whole_sign_house(_lon("Cancer", 15.0), asc) == 12
    assert hellenistic.whole_sign_house(_lon("Aquarius", 0.0), asc) == 7  # opposite


def test_place_category_angular_succedent_cadent():
    assert hellenistic.place_category(1) == "angular"
    assert hellenistic.place_category(10) == "angular"
    assert hellenistic.place_category(2) == "succedent"
    assert hellenistic.place_category(11) == "succedent"
    assert hellenistic.place_category(3) == "cadent"
    assert hellenistic.place_category(12) == "cadent"


# ---------------------------------------------------------------------------
# Triplicity lords of the sect light
# ---------------------------------------------------------------------------

def test_triplicity_lords_ordered_by_sect():
    # Air (Gemini): Dorothean day Saturn, night Mercury, participating Jupiter.
    assert hellenistic.triplicity_lords_of("Gemini", medieval.DIURNAL) == \
        ["Saturn", "Mercury", "Jupiter"]
    # Night swaps the first two (the in-sect lord leads).
    assert hellenistic.triplicity_lords_of("Gemini", medieval.NOCTURNAL) == \
        ["Mercury", "Saturn", "Jupiter"]


# ---------------------------------------------------------------------------
# Assembly: compute_hellenistic
# ---------------------------------------------------------------------------

def test_compute_hellenistic_uses_whole_sign_and_reuses_substrate():
    hc = hellenistic.compute_hellenistic(PEOPLE["alex"])
    assert hc.natal.house_system == "whole-sign"
    assert hc.sect == medieval.DIURNAL
    assert hc.sect_light == "Sun"
    assert hc.benefic_of_sect == "Jupiter"
    # Sun in Gemini with a Leo Ascendant -> 11th whole-sign house (succedent).
    sun = next(h for h in hc.whole_sign_houses if h.planet == "Sun")
    assert sun.house == 11 and sun.category == "succedent"
    # The seven Hermetic lots are reused, each with a whole-sign house.
    assert {"Fortune", "Spirit", "Eros", "Necessity", "Courage", "Victory", "Nemesis"} == set(hc.lots)
    assert set(hc.lot_houses) == set(hc.lots)
    assert 1 <= hc.lot_houses["Fortune"] <= 12
    # Triplicity lords of the sect light (Sun in Gemini/Air, diurnal).
    assert hc.triplicity_lords_of_sect_light == ["Saturn", "Mercury", "Jupiter"]


def test_hellenistic_to_dict_is_json_serializable():
    hc = hellenistic.compute_hellenistic(PEOPLE["alex"])
    d = hc.to_dict()
    assert d["kind"] == "hellenistic"
    json.dumps(d)


def test_render_hellenistic_has_key_sections():
    from render_md import render_hellenistic
    hc = hellenistic.compute_hellenistic(PEOPLE["alex"])
    md = render_hellenistic(hc)
    assert "Hellenistic" in md
    assert "Whole-Sign" in md
    assert "Sect" in md
    assert "Lots" in md
    assert "Triplicity Lords" in md
