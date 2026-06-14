"""Generate ``astro_glyphs.json`` from the bundled Astronomicon font.

The graphical chart wheel (``lib/wheel.py``) draws planet/sign/angle symbols as
SVG ``<path>`` outlines rather than as ``<text>`` in a font, so the wheel renders
identically in every rasterizer (Chrome, LibreOffice, librsvg) and in browsers
with no runtime font dependency. This one-shot generator extracts the outline of
each needed glyph from ``assets/fonts/astronomicon/Astronomicon.ttf`` and writes
their path data to ``astro_glyphs.json`` (committed to the repo).

Run from anywhere with the project venv::

    python scripts/lib/_gen_astro_glyphs.py

Requires ``fonttools`` (a dev/build dependency only — NOT needed at runtime).

Astronomicon is an ASCII-remapped font: each astrological symbol sits on a Latin
keyboard character. The mapping below was established two ways (this repo's
"verify, never recall" rule for reference tables, spec/medieval §4):

  1. The vendor's own keyboard map at https://astronomicon.co/en/astronomicon-fonts/
     (Ceres=l, Pallas=m, Juno=n, Vesta=o, Chiron=q, Eris=s, Lilith=z,
      N-Node=g, S-Node=i, Part of Fortune=?).
  2. Direct visual inspection of a rendered specimen of the font, which confirms
     the signs on A–L and the ten planets on Q–Z, and the AC/MC/IC/DC text
     ligatures on c/d/e/f, Vertex on k, and the retrograde mark ℞ on M.

Font: Astronomicon © 2021 Roberto Corona, SIL OFL v1.1, Reserved Font Name
"Astronomicon". We ship the original .ttf verbatim (no modification → the RFN
rename obligation does not apply) and derive these outlines from it.
"""
from __future__ import annotations

import json
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONT = HERE.parents[1] / "assets" / "fonts" / "astronomicon" / "Astronomicon.ttf"
OUT = HERE / "astro_glyphs.json"

# logical name (as it appears in chart JSON) -> Astronomicon keyboard character
CHAR_MAP = {
    # Zodiac signs ------------------------------------------------------------
    "Aries": "A", "Taurus": "B", "Gemini": "C", "Cancer": "D",
    "Leo": "E", "Virgo": "F", "Libra": "G", "Scorpio": "H",
    "Sagittarius": "I", "Capricorn": "J", "Aquarius": "K", "Pisces": "L",
    # Luminaries & planets ----------------------------------------------------
    "Sun": "Q", "Moon": "R", "Mercury": "S", "Venus": "T", "Mars": "U",
    "Jupiter": "V", "Saturn": "W", "Uranus": "X", "Neptune": "Y", "Pluto": "Z",
    # Asteroids / centaurs / dwarf planets ------------------------------------
    "Ceres": "l", "Pallas": "m", "Juno": "n", "Vesta": "o",
    "Chiron": "q", "Eris": "s",
    # Lunar apsis & nodes -----------------------------------------------------
    "Lilith": "z", "True Node": "g", "South Node": "i",
    # Angles (text ligatures in the font) -------------------------------------
    "Ascendant": "c", "Midheaven": "d", "IC": "e", "Descendant": "f",
    "Vertex": "k",
    # Markers -----------------------------------------------------------------
    "retrograde": "M",
}


def main() -> int:
    font = TTFont(FONT)
    upem = font["head"].unitsPerEm
    glyphset = font.getGlyphSet()
    cmap = font.getBestCmap()

    glyphs: dict[str, dict] = {}
    for name, ch in CHAR_MAP.items():
        gname = cmap[ord(ch)]
        g = glyphset[gname]
        path_pen = SVGPathPen(glyphset)
        g.draw(path_pen)
        bounds_pen = BoundsPen(glyphset)
        g.draw(bounds_pen)
        bbox = bounds_pen.bounds  # (xMin, yMin, xMax, yMax) in font units, y-up
        glyphs[name] = {
            "char": ch,
            "d": path_pen.getCommands(),
            "advance": g.width,
            "bbox": list(bbox) if bbox else None,
        }

    payload = {
        "_source": "Astronomicon v1.1 (SIL OFL), © 2021 Roberto Corona",
        "_generator": "lib/_gen_astro_glyphs.py",
        "units_per_em": upem,
        "y_axis": "up (font coords); flip y when emitting SVG",
        "glyphs": glyphs,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({len(glyphs)} glyphs, upem={upem})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
