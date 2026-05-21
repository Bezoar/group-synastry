"""Smoke tests for the .pdf renderer (Phase 2)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import chart as chart_mod  # via conftest.py path injection
import render_pdf


FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


def _have_soffice() -> bool:
    try:
        render_pdf.locate_soffice()
        return True
    except render_pdf.PdfError:
        return False


pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not _have_soffice(),
    reason="Both Node and LibreOffice (soffice) are required for the .pdf path.",
)


def test_render_natal_pdf_defaults_to_dark(tmp_path: Path) -> None:
    """render_to_pdf without --theme should produce a dark-mode PDF (DEFAULT_PDF_THEME)."""
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    out = tmp_path / "alex.pdf"
    render_pdf.render_to_pdf(chart.to_dict(), out)
    assert out.exists() and out.stat().st_size > 2000, f"pdf not produced or too small: {out}"
    assert out.read_bytes()[:5] == b"%PDF-", "output is not a PDF"
    assert render_pdf.DEFAULT_PDF_THEME == "dark", \
        "the dark-pdf default is load-bearing; downstream tests rely on it"


@pytest.mark.skipif(shutil.which("magick") is None and shutil.which("convert") is None,
                    reason="ImageMagick required to verify rendered PDF brightness.")
def test_dark_theme_pdf_is_actually_dark(tmp_path: Path) -> None:
    """Rasterize the rendered PDF and assert the page is dark (low mean brightness).

    This pins LibreOffice's behavior — when it converts a docx with a
    <w:background> element to PDF, the background must survive the export.
    If LibreOffice ever changes that default, this test catches it before
    users see a light PDF with dark-colored text on it (unreadable).
    """
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    dark = tmp_path / "alex-dark.pdf"
    light = tmp_path / "alex-light.pdf"
    render_pdf.render_to_pdf(chart.to_dict(), dark, theme="dark")
    render_pdf.render_to_pdf(chart.to_dict(), light, theme="light")
    magick = shutil.which("magick") or shutil.which("convert")
    fmt = "%[fx:int(mean*255)]"
    dark_mean = int(subprocess.check_output(
        [magick, f"{dark}[0]", "-colorspace", "RGB", "-resize", "100x100", "-format", fmt, "info:"]
    ).decode().strip())
    light_mean = int(subprocess.check_output(
        [magick, f"{light}[0]", "-colorspace", "RGB", "-resize", "100x100", "-format", fmt, "info:"]
    ).decode().strip())
    # The page bg's mean is ~27 (#1A1A24 → 26,26,36) but the page-1 mean is
    # pulled up by ~light-on-dark text. Observed at implementation time:
    # dark≈69, light≈230. Threshold is generous but the dark↔light delta is
    # the load-bearing assertion.
    assert dark_mean < 100, f"dark PDF mean brightness {dark_mean} too high; expected <100"
    assert light_mean > 180, f"light PDF mean brightness {light_mean} too low; expected >180"
    assert light_mean - dark_mean > 100, (
        f"dark and light PDFs nearly identical in brightness "
        f"(dark={dark_mean}, light={light_mean}); theme is not propagating"
    )
