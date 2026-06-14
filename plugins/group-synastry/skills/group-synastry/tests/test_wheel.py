"""Tests for the graphical chart-wheel renderer (issue #39)."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import chart as chart_mod  # via conftest.py path injection
from lib import wheel


FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


def _wheel(person_id: str = "alex", **kw) -> str:
    chart = chart_mod.compute_natal(PEOPLE[person_id], house_system="placidus").to_dict()
    return wheel.render_wheel(chart, **kw)


def _count_class(svg: str, cls: str) -> int:
    return svg.count(f'class="{cls}"')


def test_wheel_is_well_formed_svg() -> None:
    svg = _wheel()
    root = ET.fromstring(svg)  # raises if not well-formed XML
    assert root.tag.endswith("svg")
    # padded canvas; annotated (default) adds a legend strip → taller than wide
    assert root.attrib["viewBox"].startswith("-44 -44 ")
    _, _, vw, vh = (float(x) for x in root.attrib["viewBox"].split())
    assert vh > vw


def test_embedded_wheel_is_square_no_legend() -> None:
    # annotate=False (the embedded variant) is a clean square with no legend.
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus").to_dict()
    svg = wheel.render_wheel(chart, annotate=False)
    root = ET.fromstring(svg)
    _, _, vw, vh = (float(x) for x in root.attrib["viewBox"].split())
    assert vw == vh
    assert "Glyphs" not in svg  # no legend header


def test_glyph_data_covers_all_natal_bodies_and_signs() -> None:
    glyphs = wheel._GLYPHS
    for body in chart_mod.NATAL_BODIES + ("South Node",):
        assert body in glyphs, f"missing glyph path for {body}"
    for sign in wheel.SIGNS:
        assert sign in glyphs, f"missing glyph path for sign {sign}"


def test_all_bodies_are_drawn_as_planet_glyphs() -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus").to_dict()
    expected = sum(1 for p in chart["planets"] if p["name"] in wheel._GLYPHS)
    svg = wheel.render_wheel(chart)
    assert _count_class(svg, "planet") == expected == 16  # 15 bodies + South Node


def test_twelve_sign_glyphs_and_house_cusps() -> None:
    svg = _wheel()
    assert _count_class(svg, "sign") == 12
    assert _count_class(svg, "cusp") == 12  # one spoke per house cusp


def test_ascendant_is_fixed_at_the_left_horizon() -> None:
    # The screen-angle mapping must place the Ascendant at 180° (9 o'clock).
    assert wheel._phi(123.4, 123.4) == 180.0
    # Increasing longitude runs counter-clockwise: +90° longitude → bottom (90°).
    assert wheel._phi(213.4, 123.4) == 90.0


def test_major_only_is_default_and_all_includes_more() -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus").to_dict()
    has_minor = any(
        a["aspect"] not in wheel.MAJOR_ASPECTS for a in chart["aspects"]
    )
    major = wheel.render_wheel(chart, aspects="major")
    alla = wheel.render_wheel(chart, aspects="all")
    if has_minor:
        assert _count_class(alla, "aspect") > _count_class(major, "aspect")
    # major mode must never draw a non-major aspect line
    n_major_aspects = sum(
        1 for a in chart["aspects"] if a["aspect"] in wheel.MAJOR_ASPECTS
        and a["a"] in {p["name"] for p in chart["planets"]}
        and a["b"] in {p["name"] for p in chart["planets"]}
    )
    assert _count_class(major, "aspect") == n_major_aspects


def test_time_unknown_renders_partial_wheel_without_houses() -> None:
    person = json.loads(json.dumps(PEOPLE["alex"]))  # deep copy
    person["birth"]["time_accuracy"] = "unknown"
    chart = chart_mod.compute_natal(person, house_system="placidus").to_dict()
    assert chart["house_cusps"] == [] and chart["angles"] == []
    svg = wheel.render_wheel(chart)
    ET.fromstring(svg)  # still well-formed
    assert _count_class(svg, "planet") >= 15  # planets still drawn
    assert _count_class(svg, "cusp") == 0     # no house spokes
    assert "no birth time" in svg             # the on-canvas note


def test_collision_spread_separates_close_bodies() -> None:
    spread = wheel._spread([10.0, 11.0, 12.0], min_gap=7.0)
    # adjacent display angles must respect the minimum gap
    s = sorted(spread)
    assert all(b - a >= 7.0 - 1e-6 for a, b in zip(s, s[1:]))


def test_dark_theme_is_dark_field_with_light_ring_and_black_signs() -> None:
    c = wheel.colors_for("dark")
    assert c.bg == "1A1A24"            # dark field
    assert c.signs == "000000"         # black sign glyphs
    assert c.tint_opacity > 0.9        # opaque pastel ring reads light over dark
    assert c.element("fire") == wheel.WheelColors().fire  # light-mode ring tints
    svg = _wheel(theme="dark")
    assert "#1A1A24" in svg            # dark page background
    assert 'fill="#000000"' in svg     # black sign glyphs present


def test_unknown_theme_falls_back_to_light() -> None:
    assert wheel.colors_for("nope").bg == "FFFFFF"
