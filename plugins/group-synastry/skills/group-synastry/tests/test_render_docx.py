"""Smoke tests for the .docx renderer (Phase 2)."""
from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import asdict
from pathlib import Path

import pytest

import chart as chart_mod  # via conftest.py path injection
import synastry as synastry_mod
import composite as composite_mod
import render_docx
from lib import rasterize


FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node is not installed; .docx renderer requires Node 20+.",
)


def _chart_to_dict(chart: chart_mod.NatalChart) -> dict:
    return chart.to_dict()


def _assert_valid_docx(path: Path, must_contain: list[str]) -> None:
    assert path.exists() and path.stat().st_size > 1000, f"docx not produced or too small: {path}"
    assert zipfile.is_zipfile(path), f"{path} is not a valid zip (docx must be zip)"
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert "word/document.xml" in names, f"missing word/document.xml in {names}"
        body = z.read("word/document.xml").decode("utf-8", errors="replace")
    for needle in must_contain:
        assert needle in body, f"expected {needle!r} in document.xml"


def test_render_natal_docx(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex.docx"
    render_docx.render_to_docx(_chart_to_dict(chart), out, embed_wheel=False)
    _assert_valid_docx(out, must_contain=["Alex", "Gemini", "Natal"])


def test_render_synastry_docx(tmp_path: Path) -> None:
    rpt = synastry_mod.compute_synastry(PEOPLE["alex"], PEOPLE["jordan"], house_system="placidus")
    # Convert dataclasses to dicts (same shape that the CLI prints with --json).
    payload = {
        "person_a": rpt.person_a,
        "person_b": rpt.person_b,
        "chart_a": rpt.chart_a,
        "chart_b": rpt.chart_b,
        "aspects": [asdict(a) for a in rpt.aspects],
        "overlays_a_in_b": [asdict(o) for o in rpt.overlays_a_in_b],
        "overlays_b_in_a": [asdict(o) for o in rpt.overlays_b_in_a],
        "notes": rpt.notes,
    }
    out = tmp_path / "synastry.docx"
    render_docx.render_to_docx(payload, out)
    _assert_valid_docx(out, must_contain=["Synastry", "Alex", "Jordan"])


def test_render_composite_midpoint_docx(tmp_path: Path) -> None:
    comp = composite_mod.midpoint_composite(PEOPLE["alex"], PEOPLE["jordan"])
    payload = {
        "method": comp.method,
        "person_a": comp.person_a,
        "person_b": comp.person_b,
        "points": [asdict(p) for p in comp.points],
        "angles": [asdict(a) for a in comp.angles],
        "house_cusps": comp.house_cusps,
        "aspects": [asdict(a) for a in comp.aspects],
        "moment": comp.moment,
        "notes": comp.notes,
    }
    out = tmp_path / "composite.docx"
    render_docx.render_to_docx(payload, out)
    _assert_valid_docx(out, must_contain=["Midpoint Composite", "Alex", "Jordan"])


def test_kind_autodetect() -> None:
    assert render_docx.detect_kind({"overlays_a_in_b": []}) == "synastry"
    assert render_docx.detect_kind({"method": "midpoint", "points": []}) == "composite"
    assert render_docx.detect_kind({"planets": [], "display_name": "X"}) == "natal"
    with pytest.raises(render_docx.RenderError):
        render_docx.detect_kind({})


def _read_document_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


def test_dark_theme_sets_page_background_and_light_text(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex-dark.docx"
    render_docx.render_to_docx(chart.to_dict(), out, theme="dark", embed_wheel=False)
    body = _read_document_xml(out)
    # Page background is set via docx-js Document.background → <w:background w:color="..."/>
    assert 'w:background w:color="1A1A24"' in body, (
        "expected dark page background hex 1A1A24 in document.xml"
    )
    # Body text runs should carry the dark theme's light text color (E8E6F0).
    assert 'w:val="E8E6F0"' in body, (
        "expected dark theme's light text color E8E6F0 in document.xml"
    )
    # And the dark theme's table header bg should be present, not the light one.
    assert 'w:fill="2A3050"' in body, "expected dark-theme table header bg 2A3050"
    assert 'w:fill="2E3E68"' not in body, "light-theme table header bg leaked into dark output"


def test_light_theme_is_default_and_uses_white_background(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex-light.docx"
    render_docx.render_to_docx(chart.to_dict(), out, embed_wheel=False)  # no theme = use style default
    body = _read_document_xml(out)
    # Light theme page bg is white; assert dark hex is absent.
    assert "1A1A24" not in body, "dark page bg leaked into default-theme output"
    # Light-theme black body text should be present somewhere.
    assert 'w:val="000000"' in body or 'w:val="2E3E68"' in body


def test_no_interpretation_means_no_interpretation_heading(tmp_path: Path) -> None:
    """Regression guard for numbers-only users — output is data-only by default."""
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex-data-only.docx"
    render_docx.render_to_docx(chart.to_dict(), out, embed_wheel=False)
    body = _read_document_xml(out)
    assert "Interpretation" not in body, (
        "rendering without an interpretation block should not emit an "
        "'Interpretation' heading — number-only readers rely on the document "
        "ending at the Aspects table"
    )


def test_interpretation_renders_after_data_with_markdown_formatting(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    interp = {
        "sections": [
            {
                "heading": "Sun in Gemini",
                "body": (
                    "Your Sun in **Gemini** keeps the chart quick, curious, "
                    "and verbal. The energy is *restless* and "
                    "[airy](https://example.com/gemini).\n\n"
                    "- prefers breadth over depth\n"
                    "- learns fast, pivots often\n"
                ),
            },
            {
                "heading": "Moon in Cancer",
                "body": "Emotional life runs on `memory` and quiet care.",
            },
        ]
    }
    out = tmp_path / "alex-with-interp.docx"
    render_docx.render_to_docx(chart.to_dict(), out, interpretation=interp, embed_wheel=False)
    body = _read_document_xml(out)
    with zipfile.ZipFile(out) as z:
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")

    # Interpretation heading is present.
    assert ">Interpretation<" in body, "missing Interpretation heading"
    assert ">Sun in Gemini<" in body
    assert ">Moon in Cancer<" in body

    # Body prose lands — but only the inline-token leaves, not the full markdown string.
    assert ">Your Sun in <" in body, "leading text of first section missing"
    assert ">Gemini<" in body
    assert ">airy<" in body, "link text should appear as a run"
    # Hyperlink targets live in the rels file, not document.xml.
    assert "example.com/gemini" in rels, "link href should be in document.xml.rels"

    # Bullet list rendered with bullet prefix.
    assert "•" in body, "bullet glyph from list rendering missing"

    # Data comes BEFORE interpretation — assert ordering by byte index.
    aspects_idx = body.find(">Notable Aspects<")
    interp_idx = body.find(">Interpretation<")
    assert aspects_idx != -1 and interp_idx != -1
    assert aspects_idx < interp_idx, (
        "Interpretation must come after the chart data so number-only readers "
        f"can stop at the Aspects section (Aspects at {aspects_idx}, "
        f"Interpretation at {interp_idx})"
    )


def _media_pngs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        return [n for n in z.namelist() if n.startswith("word/media/")]


@pytest.mark.skipif(
    rasterize.available_backend() is None,
    reason="no SVG rasterizer (Chrome/LibreOffice) available for wheel embedding",
)
def test_natal_docx_embeds_wheel_below_heading_above_tables(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex-wheel.docx"
    render_docx.render_to_docx(chart.to_dict(), out)
    assert _media_pngs(out), "expected an embedded wheel PNG in word/media/"
    body = _read_document_xml(out)
    title_idx = body.find("Western Tropical Natal Chart")
    img_idx = body.find("<w:drawing>")
    pos_idx = body.find("Planets and Points")
    assert img_idx != -1, "no image drawing found in natal docx"
    # wheel sits below the heading and above the positions table
    assert 0 <= title_idx < img_idx < pos_idx, (
        f"expected heading({title_idx}) < wheel({img_idx}) < positions({pos_idx})"
    )


def test_no_wheel_opts_out_of_embedding(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex-nowheel.docx"
    render_docx.render_to_docx(chart.to_dict(), out, embed_wheel=False)
    assert not _media_pngs(out), "embed_wheel=False must not embed an image"


def test_synastry_report_has_no_wheel(tmp_path: Path) -> None:
    rpt = synastry_mod.compute_synastry(PEOPLE["alex"], PEOPLE["jordan"], house_system="placidus")
    payload = {
        "person_a": rpt.person_a, "person_b": rpt.person_b,
        "chart_a": rpt.chart_a, "chart_b": rpt.chart_b,
        "aspects": [asdict(a) for a in rpt.aspects],
        "overlays_a_in_b": [asdict(o) for o in rpt.overlays_a_in_b],
        "overlays_b_in_a": [asdict(o) for o in rpt.overlays_b_in_a],
        "notes": rpt.notes,
    }
    out = tmp_path / "syn-nowheel.docx"
    render_docx.render_to_docx(payload, out)
    assert not _media_pngs(out), "wheel embedding is natal-only"


def test_missing_rasterizer_degrades_to_text_only(tmp_path: Path, monkeypatch) -> None:
    """A natal report must still render (text-only) if no rasterizer is present."""
    def _boom(*a, **k):
        raise rasterize.RasterizeError("simulated: no rasterizer")
    monkeypatch.setattr(render_docx, "build_wheel_png_b64", _boom)
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex-degraded.docx"
    render_docx.render_to_docx(chart.to_dict(), out)  # must not raise
    _assert_valid_docx(out, must_contain=["Alex", "Planets and Points"])
    assert not _media_pngs(out)


def test_interpretation_section_ends_with_disclaimer(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    interp = {"sections": [{"heading": "Sun", "body": "Bright and central."}]}
    out = tmp_path / "alex-disclaimer.docx"
    render_docx.render_to_docx(chart.to_dict(), out, interpretation=interp, embed_wheel=False)
    body = _read_document_xml(out)
    assert "not a substitute for human intuition" in body
    assert "For entertainment purposes only" in body
    # disclaimer comes after the interpretation heading
    assert body.find(">Interpretation<") < body.find("not a substitute for human intuition")


def test_no_disclaimer_without_interpretation(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex-nodisc.docx"
    render_docx.render_to_docx(chart.to_dict(), out, embed_wheel=False)
    body = _read_document_xml(out)
    assert "entertainment purposes only" not in body


def test_markdown_interpretation_has_disclaimer() -> None:
    import render_md
    md = render_md.render_interpretation({"sections": [{"heading": "X", "body": "y"}]})
    assert "_Automated interpretation is not a substitute for human intuition." in md
    assert "For entertainment purposes only._" in md
    assert render_md.render_interpretation(None) == ""  # none when no interpretation


def test_interpretation_via_chart_dict_field_is_also_honored(tmp_path: Path) -> None:
    """Callers may pre-merge interpretation into the chart dict (which is what
    the --interpretation FILE CLI flag does)."""
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus").to_dict()
    chart["interpretation"] = {
        "sections": [{"heading": "Quick note", "body": "Just a smoke test."}]
    }
    out = tmp_path / "alex-merged-interp.docx"
    render_docx.render_to_docx(chart, out, embed_wheel=False)
    body = _read_document_xml(out)
    assert ">Quick note<" in body
    assert ">Just a smoke test.<" in body
