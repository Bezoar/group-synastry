"""Tests for interpretation persistence and round-tripping.

Covers the two gaps closed after Phase 1.5 initial commit:

* ``chart.py / synastry.py / composite.py`` accept ``--interpretation FILE``
  and append the prose to the markdown output, matching the docx/pdf path.
* ``render_docx.py / render_pdf.py`` write a ``<output>.interpretation.md``
  sidecar by default when ``--interpretation`` was given; ``--no-sidecar``
  suppresses it.
* The sidecar format round-trips through ``parse_interpretation_file()``
  back to the canonical ``{"sections": [...]}`` dict.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

import chart as chart_mod
import render_docx


FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


SAMPLE_INTERP = {
    "sections": [
        {
            "heading": "Sun in Gemini, 11th house",
            "body": "Anchored, **embodied**, *relational*.\n\n- patient\n- consistent\n",
        },
        {
            "heading": "Moon in Cancer, 12th house",
            "body": "Runs on `analysis` and quiet care.",
        },
    ]
}


# ---- chart.py / synastry.py / composite.py --interpretation -------------

def _isolated_db(tmp_path: Path, monkeypatch) -> None:
    """Point the chart scripts at a tmp people.json with Alex + Jordan."""
    cfg = tmp_path / "group-synastry"
    cfg.mkdir()
    (cfg / "people.json").write_text(json.dumps({
        "version": 1,
        "people": [PEOPLE["alex"], PEOPLE["jordan"]],
    }))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_chart_py_natal_with_interpretation_appends_section(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _isolated_db(tmp_path, monkeypatch)
    interp_path = tmp_path / "interp.json"
    interp_path.write_text(json.dumps(SAMPLE_INTERP))

    rc = chart_mod._main(["natal", "alex", "--interpretation", str(interp_path)])
    assert rc == 0

    out = capsys.readouterr().out
    assert "## Interpretation" in out, "interpretation header missing from markdown output"
    assert "### Sun in Gemini, 11th house" in out
    assert "### Moon in Cancer, 12th house" in out
    # Body markdown is emitted verbatim — preserves the user's formatting.
    assert "**embodied**" in out
    assert "- patient" in out

    # Data block precedes interpretation in the markdown stream.
    data_idx = out.find("## Planets and Points")
    interp_idx = out.find("## Interpretation")
    assert 0 <= data_idx < interp_idx, "interpretation must come after the data tables"


def test_chart_py_with_interpretation_json_via_kind_natal(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """--json mode ignores --interpretation (the prose is for the markdown path)."""
    _isolated_db(tmp_path, monkeypatch)
    interp_path = tmp_path / "interp.json"
    interp_path.write_text(json.dumps(SAMPLE_INTERP))

    rc = chart_mod._main(["natal", "alex", "--json", "--interpretation", str(interp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    # JSON output is chart data only; interpretation didn't get embedded.
    assert "interpretation" not in payload


# ---- Sidecar emission on the docx side ----------------------------------

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node is required to exercise the docx renderer.",
)


def test_render_to_docx_writes_sidecar_when_interpretation_given_via_cli(
    tmp_path: Path
) -> None:
    """The CLI path (render_docx.py._main) writes the sidecar; the library
    function does not (it leaves persistence to the caller)."""
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    chart_json = tmp_path / "chart.json"
    chart_json.write_text(json.dumps(chart.to_dict(), default=str))
    interp_path = tmp_path / "interp.json"
    interp_path.write_text(json.dumps(SAMPLE_INTERP))
    out = tmp_path / "alex.docx"

    rc = render_docx._main([
        "--input", str(chart_json),
        "--output", str(out),
        "--interpretation", str(interp_path),
    ])
    assert rc == 0
    sidecar = tmp_path / "alex.interpretation.md"
    assert sidecar.exists(), f"sidecar not written next to {out}"

    body = sidecar.read_text()
    assert "## Sun in Gemini, 11th house" in body
    assert "**embodied**" in body, "section body markdown should be preserved"
    assert "_Auto-generated" in body, "sidecar should carry an auto-gen header"


def test_no_sidecar_flag_suppresses_sidecar(tmp_path: Path) -> None:
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    chart_json = tmp_path / "chart.json"
    chart_json.write_text(json.dumps(chart.to_dict(), default=str))
    interp_path = tmp_path / "interp.json"
    interp_path.write_text(json.dumps(SAMPLE_INTERP))
    out = tmp_path / "alex.docx"

    rc = render_docx._main([
        "--input", str(chart_json),
        "--output", str(out),
        "--interpretation", str(interp_path),
        "--no-sidecar",
    ])
    assert rc == 0
    assert not (tmp_path / "alex.interpretation.md").exists(), "--no-sidecar failed"


# ---- Round-trip: JSON → render → sidecar.md → parse → equivalent dict ---

def test_sidecar_round_trips_through_parse_interpretation_file(tmp_path: Path) -> None:
    """The sidecar markdown must be parseable back into the same shape so
    users can edit the sidecar, re-render, and have the new prose flow back
    into the document."""
    sidecar = tmp_path / "round-trip.interpretation.md"
    sidecar.write_text("\n".join([
        "# Some title",
        "",
        "_Auto-generated comment line._",
        "",
        "## Heading One",
        "",
        "Body **one** with *emphasis*.",
        "",
        "## Heading Two",
        "",
        "Body two.",
        "More body two.",
        "",
    ]))
    parsed = render_docx.parse_interpretation_file(sidecar)
    assert parsed == {
        "sections": [
            {"heading": "Heading One", "body": "Body **one** with *emphasis*."},
            {"heading": "Heading Two", "body": "Body two.\nMore body two."},
        ]
    }


def test_parse_interpretation_file_rejects_unknown_extension(tmp_path: Path) -> None:
    bogus = tmp_path / "interp.yaml"
    bogus.write_text("sections: []")
    with pytest.raises(render_docx.RenderError):
        render_docx.parse_interpretation_file(bogus)


def test_md_sidecar_can_be_used_as_interpretation_input(tmp_path: Path) -> None:
    """End-to-end loop: write JSON interp → render docx + sidecar → use the
    sidecar as the next --interpretation input → both docx files contain
    the same section headings in document.xml."""
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    chart_json = tmp_path / "chart.json"
    chart_json.write_text(json.dumps(chart.to_dict(), default=str))
    interp_path = tmp_path / "interp.json"
    interp_path.write_text(json.dumps(SAMPLE_INTERP))

    out1 = tmp_path / "first.docx"
    assert render_docx._main([
        "--input", str(chart_json), "--output", str(out1),
        "--interpretation", str(interp_path),
    ]) == 0

    sidecar = tmp_path / "first.interpretation.md"
    assert sidecar.exists()

    out2 = tmp_path / "second.docx"
    assert render_docx._main([
        "--input", str(chart_json), "--output", str(out2),
        "--interpretation", str(sidecar),
        "--no-sidecar",
    ]) == 0

    def _section_headings(p: Path) -> set[str]:
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        return {
            section["heading"]
            for section in SAMPLE_INTERP["sections"]
            if f">{section['heading']}<" in xml
        }

    assert _section_headings(out1) == _section_headings(out2) == {
        "Sun in Gemini, 11th house", "Moon in Cancer, 12th house",
    }
