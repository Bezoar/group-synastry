"""Graphical natal chart-wheel renderer (issue #39).

Pure-Python SVG generation — no third-party runtime dependency. Astrological
symbols are drawn as SVG ``<path>`` outlines (data in ``astro_glyphs.json``,
derived from the bundled Astronomicon font) so the wheel renders identically in
browsers and in every rasterizer (Chrome, LibreOffice, librsvg), which matters
for the PNG that gets embedded into the .docx/.pdf reports.

Entry point: :func:`render_wheel(chart, ...) -> str` returning an SVG document.

All geometry lives in :class:`WheelGeometry` and the colour tokens in
:class:`WheelColors` so the look can be pixel-pushed without touching the
drawing code.

Coordinate convention
---------------------
Ecliptic longitude ``λ`` maps to a screen angle ``φ = 180 - (λ - asc_lon)``
(degrees). With SVG's y-pointing-down, that fixes the Ascendant at the left
(9 o'clock) and makes increasing longitude run counter-clockwise: 2nd/3rd
houses downward, IC at bottom, Descendant right, MC top — the conventional
wheel. When the birth time is unknown there are no angles; we fall back to
0° Aries at the left and omit houses/angles (partial wheel).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_GLYPHS_PATH = Path(__file__).resolve().parent / "astro_glyphs.json"
_GLYPH_DATA = json.loads(_GLYPHS_PATH.read_text())
_UPEM = _GLYPH_DATA["units_per_em"]
_GLYPHS = _GLYPH_DATA["glyphs"]

SIGNS = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)
# Element of each sign, in zodiac order — drives the pastel band tint.
_ELEMENTS = (
    "fire", "earth", "air", "water",
    "fire", "earth", "air", "water",
    "fire", "earth", "air", "water",
)

# Aspect families → line colour bucket (decision #7: red=hard, blue=soft,
# grey=minor; conjunction is neither hard nor soft, drawn neutral).
_ASPECT_FAMILY = {
    "conjunction": "conjunction",
    "opposition": "hard", "square": "hard",
    "trine": "soft", "sextile": "soft",
    "quincunx": "minor", "semisextile": "minor",
    "semisquare": "minor", "sesquisquare": "minor",
}
MAJOR_ASPECTS = {"conjunction", "opposition", "trine", "square", "sextile"}


@dataclass
class WheelGeometry:
    """All radii/sizes in user units on a square ``size``×``size`` canvas."""
    size: float = 1000.0
    pad: float = 44.0               # blank margin around the wheel (room for outside labels)
    r_outer: float = 460.0          # outermost circle (leaves edge margin for angle labels)
    r_zodiac_in: float = 415.0      # inner edge of the zodiac band
    r_sign: float = 438.0           # sign-glyph centreline
    r_tick_minor: float = 415.0     # minor degree ticks start here, go out by..
    tick_minor_len: float = 8.0
    tick_major_len: float = 15.0    # every 10°
    r_planet: float = 372.0         # planet-glyph centreline (after fan-out)
    r_planet_mark: float = 410.0    # tick at a planet's TRUE longitude
    r_label: float = 335.0          # degree readout centreline
    r_house_in: float = 235.0       # inner hub; aspect lines live inside this
    r_cusp_out: float = 415.0       # house-cusp spokes run r_house_in..here
    r_house_num: float = 252.0      # house-number ring
    glyph_planet: float = 40.0      # planet glyph em size
    glyph_sign: float = 34.0        # sign glyph em size
    glyph_label_sign: float = 16.0  # tiny sign glyph inside a degree readout
    label_pt: float = 15.0          # degree readout font size
    house_num_pt: float = 15.0
    angle_label_pt: float = 26.0    # Asc/MC/Dsc/IC labels outside the ring
    angle_off_side: float = 34.0    # radial offset of the Asc/Dsc labels
    angle_off_tb: float = 22.0      # radial offset of the MC/IC labels
    min_planet_gap_deg: float = 7.0  # collision fan-out threshold
    # standalone annotations (title corner + legend gutter; omitted when embedded)
    title_pt: float = 26.0
    subtitle_pt: float = 16.0
    legend_h: float = 230.0         # extra canvas height reserved for the legend
    legend_cols: int = 4
    legend_col_w: float = 200.0     # width of one legend column (glyph + name)
    legend_row: float = 40.0
    legend_glyph: float = 44.0
    legend_pt: float = 22.0
    legend_box_pad: float = 16.0    # inner padding of the legend box


@dataclass
class WheelColors:
    bg: str = "FFFFFF"
    ink: str = "1A1A24"            # planet glyphs
    sign_ink: Optional[str] = None  # sign glyphs (falls back to `ink` if None)
    ring: str = "8A85A0"
    tick: str = "9A95AC"
    cusp: str = "B8B4C8"
    angle_cusp: str = "5A5470"
    label: str = "3A3550"
    leader: str = "B0ACC0"
    aspect_hard: str = "C0392B"
    aspect_soft: str = "2C6FB0"
    aspect_conjunction: str = "6A6480"
    aspect_minor: str = "B7A86A"
    tint_opacity: float = 0.62     # zodiac-band fill opacity
    # pastel element tints for the zodiac band (a touch more saturated than
    # true pastels so adjacent-element boundaries — e.g. Aquarius/Pisces,
    # Virgo/Libra — stay distinct)
    fire: str = "F2C3B6"
    earth: str = "CFDFB2"
    air: str = "EFE5A6"
    water: str = "BCD7E9"

    def element(self, el: str) -> str:
        return {"fire": self.fire, "earth": self.earth,
                "air": self.air, "water": self.water}[el]

    @property
    def signs(self) -> str:
        return self.sign_ink or self.ink


# Dark theme: dark field, but with the light pastel zodiac ring (drawn opaque so
# it reads light over the dark page), black sign glyphs, and bright body→dial
# indicator lines / house cusps / angle markers.
_DARK = WheelColors(
    bg="1A1A24", ink="E8E6F0", sign_ink="000000",
    ring="6A6480", tick="6A6480",
    cusp="C2BCD6",          # house-cusp spokes as sharp as the indicator lines
    angle_cusp="F0EEF8",    # bright Asc/Dsc/IC/MC (labels + angular spokes)
    label="C8C4D8", leader="C2BCD6", tint_opacity=0.95,
    # hard=red brightened to match the soft=blue luminance on the dark field
    aspect_hard="F07D6F", aspect_soft="6FA8DA", aspect_conjunction="A39CC0",
    aspect_minor="C9B978",
    fire="F2C3B6", earth="CFDFB2", air="EFE5A6", water="BCD7E9",
)

_THEMES = {"light": WheelColors(), "dark": _DARK}


def colors_for(theme: str) -> WheelColors:
    """Wheel colour palette for a theme name; unknown names fall back to light."""
    return _THEMES.get(theme, _THEMES["light"])


# --------------------------------------------------------------------------
# Low-level SVG helpers
# --------------------------------------------------------------------------

def _polar(cx: float, cy: float, r: float, phi_deg: float) -> tuple[float, float]:
    a = math.radians(phi_deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def _phi(lon: float, asc_lon: float) -> float:
    """Ecliptic longitude → screen angle (degrees). See module docstring."""
    return (180.0 - (lon - asc_lon)) % 360.0


def _fmt(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".")


def _arc_points(cx, cy, r, phi1, phi2, step=2.0) -> list[tuple[float, float]]:
    """Sample an arc from phi1→phi2 (increasing) as points; robust vs SVG arc
    flags, and good enough at 2° steps for circles/bands/wedges."""
    if phi2 < phi1:
        phi2 += 360.0
    n = max(2, int(math.ceil((phi2 - phi1) / step)) + 1)
    return [_polar(cx, cy, r, phi1 + (phi2 - phi1) * i / (n - 1)) for i in range(n)]


def _poly(points: list[tuple[float, float]], *, fill="none", stroke="none",
          width=1.0, opacity=None, closed=False) -> str:
    d = "M" + " L".join(f"{_fmt(x)},{_fmt(y)}" for x, y in points)
    if closed:
        d += " Z"
    op = f' fill-opacity="{opacity}"' if opacity is not None else ""
    return (f'<path d="{d}" fill="{_hex(fill)}"{op} stroke="{_hex(stroke)}" '
            f'stroke-width="{_fmt(width)}"/>')


def _hex(c: str) -> str:
    if c == "none":
        return "none"
    return c if c.startswith("#") else f"#{c}"


def _line(x1, y1, x2, y2, stroke, width=1.0, opacity=None, dash=None, cls=None) -> str:
    op = f' stroke-opacity="{opacity}"' if opacity is not None else ""
    da = f' stroke-dasharray="{dash}"' if dash else ""
    cl = f' class="{cls}"' if cls else ""
    return (f'<line{cl} x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" '
            f'y2="{_fmt(y2)}" stroke="{_hex(stroke)}" '
            f'stroke-width="{_fmt(width)}"{op}{da}/>')


def _circle(cx, cy, r, *, fill="none", stroke="none", width=1.0) -> str:
    return (f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(r)}" '
            f'fill="{_hex(fill)}" stroke="{_hex(stroke)}" stroke-width="{_fmt(width)}"/>')


def _text(x, y, s, *, size, color, anchor="middle", weight="normal") -> str:
    return (f'<text x="{_fmt(x)}" y="{_fmt(y)}" font-size="{_fmt(size)}" '
            f'fill="{_hex(color)}" text-anchor="{anchor}" '
            f'font-family="Helvetica,Arial,sans-serif" font-weight="{weight}" '
            f'dominant-baseline="central">{_xml(s)}</text>')


def _xml(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _approx_text_w(s: str, size: float) -> float:
    """Rough width of a bold sans-serif string at *size* px (~0.6 em/char).
    Good enough to line annotations up against centre-anchored labels."""
    return 0.6 * size * len(s)


def _glyph(name: str, gx: float, gy: float, size: float, color: str,
           cls: Optional[str] = None) -> str:
    """Draw an Astronomicon glyph centred at (gx,gy) at em-size *size*."""
    g = _GLYPHS.get(name)
    if not g or not g.get("bbox"):
        return ""
    s = size / _UPEM
    bx0, by0, bx1, by1 = g["bbox"]
    bcx, bcy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    # translate to target, flip y (font y-up → svg y-down), centre on bbox.
    tf = (f"translate({_fmt(gx)},{_fmt(gy)}) scale({_fmt(s)},{_fmt(-s)}) "
          f"translate({_fmt(-bcx)},{_fmt(-bcy)})")
    cl = f' class="{cls}"' if cls else ""
    return f'<g{cl} transform="{tf}"><path d="{g["d"]}" fill="{_hex(color)}"/></g>'


# --------------------------------------------------------------------------
# Collision fan-out
# --------------------------------------------------------------------------

def _spread(phis: list[float], min_gap: float) -> list[float]:
    """Spread a set of angles (deg, on a circle) so neighbours are at least
    *min_gap* apart while preserving their cyclic order and staying near the
    originals. Returns new angles aligned to the *input* order.

    Method: break the circle at its largest gap (the natural empty wedge),
    unwrap the rest into a monotonic line, run an order-preserving forward
    min-gap pass, then re-centre so the cluster doesn't drift. Exact for the
    ≤17 bodies on a wheel, where n·min_gap ≪ 360°."""
    n = len(phis)
    if n < 2:
        return list(phis)
    order = sorted(range(n), key=lambda i: phis[i] % 360.0)
    a = [phis[i] % 360.0 for i in order]
    gaps = [(a[(i + 1) % n] - a[i]) % 360.0 for i in range(n)]
    start = max(range(n), key=lambda i: gaps[i])  # big gap sits after index `start`
    seq = [(start + 1 + k) % n for k in range(n)]  # walk forward from the gap
    # unwrap the sequence's true angles into a monotonic line
    raw = [a[seq[0]]]
    for k in range(1, n):
        v = a[seq[k]]
        while v < raw[-1]:
            v += 360.0
        raw.append(v)
    # forward min-gap pass
    pos = [raw[0]]
    for k in range(1, n):
        pos.append(max(raw[k], pos[-1] + min_gap))
    # re-centre: cancel the mean displacement so the spread sits over the cluster
    shift = sum(p - r for p, r in zip(pos, raw)) / n
    out = [0.0] * n
    for k, si in enumerate(seq):
        out[order[si]] = (pos[k] - shift) % 360.0
    return out


# --------------------------------------------------------------------------
# Chart-shaped helpers
# --------------------------------------------------------------------------

def _asc_longitude(chart: dict) -> Optional[float]:
    for a in chart.get("angles", []) or []:
        if a.get("name") == "Ascendant":
            return float(a["longitude"])
    return None


_ANGLE_ABBR = {"Ascendant": "Asc", "Midheaven": "MC", "Descendant": "Dsc",
               "IC": "IC", "Vertex": "Vx"}


# --------------------------------------------------------------------------
# Main renderer
# --------------------------------------------------------------------------

def render_wheel(
    chart: dict,
    *,
    theme: str = "light",
    aspects: str = "major",
    show_tints: bool = True,
    annotate: bool = True,
    geometry: Optional[WheelGeometry] = None,
    colors: Optional[WheelColors] = None,
) -> str:
    """Render *chart* (a natal chart dict, as emitted by ``chart.py --json``) to
    an SVG document string.

    ``aspects``: ``"major"`` (conj/opp/trine/square/sextile, default) or
    ``"all"`` (everything in ``chart['aspects']``).

    ``annotate``: when ``True`` (the standalone default) the wheel carries a
    title in the upper-left gutter and a glyph legend in a strip below the
    wheel. When ``False`` (used for the PNG embedded into reports, where the
    document already supplies the title and the tables name every body) the
    wheel is drawn clean with no title/legend.
    """
    g = geometry or WheelGeometry()
    c = colors or colors_for(theme)
    cx = cy = g.size / 2.0

    asc = _asc_longitude(chart)
    has_houses = bool(chart.get("house_cusps")) and asc is not None
    asc_lon = asc if asc is not None else 0.0

    out: list[str] = []
    vb_w = g.size + 2 * g.pad
    vb_h = vb_w + (g.legend_h if annotate else 0.0)
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(vb_w)}" '
        f'height="{_fmt(vb_h)}" viewBox="{_fmt(-g.pad)} {_fmt(-g.pad)} '
        f'{_fmt(vb_w)} {_fmt(vb_h)}">'
    )
    # page background fills the whole padded canvas (so dark-theme corners fill too)
    out.append(f'<rect x="{_fmt(-g.pad)}" y="{_fmt(-g.pad)}" width="{_fmt(vb_w)}" '
               f'height="{_fmt(vb_h)}" fill="{_hex(c.bg)}"/>')

    # ---- zodiac band: per-sign pastel wedges + sign glyphs ----------------
    for i, sign in enumerate(SIGNS):
        lon0, lon1 = i * 30.0, (i + 1) * 30.0
        phi_a, phi_b = _phi(lon1, asc_lon), _phi(lon0, asc_lon)  # lon↑ ⇒ phi↓
        if show_tints:
            outer = _arc_points(cx, cy, g.r_outer, phi_a, phi_b)
            inner = _arc_points(cx, cy, g.r_zodiac_in, phi_a, phi_b)
            out.append(_poly(outer + inner[::-1], fill=c.element(_ELEMENTS[i]),
                             opacity=c.tint_opacity, closed=True))
        gx, gy = _polar(cx, cy, g.r_sign, _phi(lon0 + 15.0, asc_lon))
        out.append(_glyph(sign, gx, gy, g.glyph_sign, c.signs, cls="sign"))

    # ring circles
    out.append(_circle(cx, cy, g.r_outer, stroke=c.ring, width=2.0))
    out.append(_circle(cx, cy, g.r_zodiac_in, stroke=c.ring, width=1.5))
    out.append(_circle(cx, cy, g.r_house_in, stroke=c.ring, width=1.5))

    # ---- degree ticks (every 1°, longer every 10°) -----------------------
    for d in range(360):
        phi = _phi(float(d), asc_lon)
        is_major = (d % 10 == 0)
        ln = g.tick_major_len if is_major else g.tick_minor_len
        x1, y1 = _polar(cx, cy, g.r_zodiac_in, phi)
        x2, y2 = _polar(cx, cy, g.r_zodiac_in + ln, phi)
        out.append(_line(x1, y1, x2, y2, c.tick, width=1.4 if is_major else 0.7))

    # ---- houses: cusp spokes + numbers -----------------------------------
    if has_houses:
        cusps = [float(x) for x in chart["house_cusps"]]
        angle_lons = {a["name"]: float(a["longitude"]) for a in chart.get("angles", [])}
        for hi, cusp in enumerate(cusps):
            phi = _phi(cusp, asc_lon)
            x1, y1 = _polar(cx, cy, g.r_house_in, phi)
            x2, y2 = _polar(cx, cy, g.r_cusp_out, phi)
            # The four angular cusps (1/4/7/10) get a heavier line.
            is_angle = hi in (0, 3, 6, 9)
            out.append(_line(x1, y1, x2, y2,
                             c.angle_cusp if is_angle else c.cusp,
                             width=2.2 if is_angle else 1.0, cls="cusp"))
            # house number placed at the midpoint of this cusp and the next
            nxt = cusps[(hi + 1) % 12]
            span = (nxt - cusp) % 360.0
            mid = cusp + span / 2.0
            nx, ny = _polar(cx, cy, g.r_house_num, _phi(mid, asc_lon))
            out.append(_text(nx, ny, str(hi + 1), size=g.house_num_pt,
                             color=c.label))
        # angle labels (Asc/MC/Dsc/IC) just outside the outer ring. The side
        # labels (Asc/Dsc) read their gap horizontally against the text's width;
        # the top/bottom ones (MC/IC) against its much-smaller height — so MC/IC
        # use a smaller radial offset to keep the visual gap to the ring even.
        _angle_off = {"Ascendant": g.angle_off_side, "Descendant": g.angle_off_side,
                      "Midheaven": g.angle_off_tb, "IC": g.angle_off_tb}
        for nm in ("Ascendant", "Midheaven", "Descendant", "IC"):
            if nm in angle_lons:
                phi = _phi(angle_lons[nm], asc_lon)
                lx, ly = _polar(cx, cy, g.r_outer + _angle_off[nm], phi)
                out.append(_text(lx, ly, _ANGLE_ABBR[nm], size=g.angle_label_pt,
                                 color=c.angle_cusp, weight="bold"))

    # ---- planets: collision fan-out, glyph, true-position tick, readout ---
    planets = [p for p in chart.get("planets", []) if p.get("name") in _GLYPHS]
    true_phi = [_phi(float(p["longitude"]), asc_lon) for p in planets]
    disp_phi = _spread(true_phi, g.min_planet_gap_deg)
    for p, tphi, dphi in zip(planets, true_phi, disp_phi):
        # tick at true ecliptic position on the zodiac inner edge
        tx, ty = _polar(cx, cy, g.r_zodiac_in, tphi)
        mx, my = _polar(cx, cy, g.r_planet_mark, tphi)
        out.append(_line(tx, ty, mx, my, c.leader, width=1.0))
        # leader from true-position mark to the (possibly fanned) glyph
        gx, gy = _polar(cx, cy, g.r_planet, dphi)
        if abs((dphi - tphi + 180) % 360 - 180) > 0.3:
            out.append(_line(mx, my, gx, gy, c.leader, width=0.8))
        out.append(_glyph(p["name"], gx, gy, g.glyph_planet, c.ink, cls="planet"))
        # degree readout inward of the glyph: "DD° <sign> MM'" (+ ℞)
        lx, ly = _polar(cx, cy, g.r_label, dphi)
        deg = f"{int(p['degree'])}°"
        mins = f"{int(p['minute']):02d}'"
        out.append(_text(lx, ly + 1, deg, size=g.label_pt, color=c.label))
        out.append(_glyph(p["sign"], lx, ly - 16, g.glyph_label_sign, c.label))
        out.append(_text(lx, ly + 17, mins, size=g.label_pt - 2, color=c.label))
        if p.get("retrograde"):
            out.append(_glyph("retrograde", lx + 20, ly + 17, 16, c.aspect_hard))

    # ---- aspect web (drawn inside the hub) -------------------------------
    want_all = aspects == "all"
    idx = {p["name"]: float(p["longitude"]) for p in planets}
    for a in chart.get("aspects", []) or []:
        kind = a.get("aspect")
        if not want_all and kind not in MAJOR_ASPECTS:
            continue
        if a["a"] not in idx or a["b"] not in idx:
            continue
        family = _ASPECT_FAMILY.get(kind, "minor")
        col = {"hard": c.aspect_hard, "soft": c.aspect_soft,
               "conjunction": c.aspect_conjunction, "minor": c.aspect_minor}[family]
        x1, y1 = _polar(cx, cy, g.r_house_in, _phi(idx[a["a"]], asc_lon))
        x2, y2 = _polar(cx, cy, g.r_house_in, _phi(idx[a["b"]], asc_lon))
        dash = "4,4" if family == "minor" else None
        out.append(_line(x1, y1, x2, y2, col, width=1.1, opacity=0.85, dash=dash,
                         cls="aspect"))

    # ---- time-unknown caution stays in the hub (it's a warning) ----------
    name = chart.get("display_name", "")
    hs = chart.get("house_system", "")
    if not has_houses:
        out.append(_circle(cx, cy, 70, fill=c.bg))
        out.append(_text(cx, cy - 8, "no birth time", size=14, color=c.aspect_hard))
        out.append(_text(cx, cy + 12, "houses & angles omitted", size=11, color=c.aspect_hard))

    # ---- standalone annotations: title (upper-left) + legend (bottom) -----
    if annotate:
        # Line the title's left edge up with the Asc label (always at φ=180, so
        # its centre x is fixed) and its first line up with the MC label height.
        asc_cx = cx - (g.r_outer + g.angle_off_side)
        tx = asc_cx - 0.5 * _approx_text_w("Asc", g.angle_label_pt)
        mc_lon = next((a["longitude"] for a in chart.get("angles", [])
                       if a["name"] == "Midheaven"), None)
        if mc_lon is not None:
            ty = cy + (g.r_outer + g.angle_off_tb) * math.sin(
                math.radians(_phi(float(mc_lon), asc_lon)))
        else:
            ty = -g.pad + g.title_pt
        out.append(_text(tx, ty, name, size=g.title_pt,
                         color=c.ink, anchor="start", weight="bold"))
        b = chart.get("birth", {})
        sub_lines = [
            _birth_when(b),
            _birth_where(b),
            f"{hs} houses" if has_houses else "natal chart (no birth time)",
        ]
        ly = ty + g.title_pt * 0.85
        for line in sub_lines:
            if line:
                out.append(_text(tx, ly, line, size=g.subtitle_pt,
                                 color=c.label, anchor="start"))
                ly += g.subtitle_pt + 5.0
        out.extend(_legend(chart, g, c, asc_lon))

    out.append("</svg>")
    return "\n".join(out)


def _birth_when(b: dict) -> str:
    """Birth date/time line for the standalone title block."""
    date, tz = b.get("date", ""), b.get("tz", "")
    if b.get("time_accuracy") == "unknown" or not b.get("time"):
        return f"{date} (time unknown)" + (f" · {tz}" if tz else "")
    return f"{date} {b['time']}" + (f" ({tz})" if tz else "")


def _birth_where(b: dict) -> str:
    """Birth place line: 'City, ST · 39.96°N, 82.96°W'."""
    lat, lon = b.get("lat"), b.get("lon")
    coords = ""
    if lat is not None and lon is not None:
        coords = (f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}, "
                  f"{abs(lon):.2f}°{'E' if lon >= 0 else 'W'}")
    label = b.get("place_label") or ""
    return " · ".join(x for x in (label, coords) if x)


def _legend(chart: dict, g: WheelGeometry, c: WheelColors, asc_lon: float) -> list[str]:
    """Body-glyph legend in a centred box below the wheel, in ``g.legend_cols``
    tight columns. Lists every body actually drawn on this wheel. The box is
    centred vertically between the bottom of the IC label and the image bottom."""
    items = [p["name"] for p in chart.get("planets", []) if p["name"] in _GLYPHS]
    if not items:
        return []
    cols = g.legend_cols
    rows = (len(items) + cols - 1) // cols
    bp, cw, rh = g.legend_box_pad, g.legend_col_w, g.legend_row
    header_h = 26.0
    box_w = cols * cw + 2 * bp
    box_h = header_h + rows * rh + 2 * bp
    box_x = g.size / 2.0 - box_w / 2.0       # centred under the wheel
    # centre the box between the bottom of the IC label and the canvas bottom
    cy = g.size / 2.0
    ic_lon = next((a["longitude"] for a in chart.get("angles", [])
                   if a["name"] == "IC"), None)
    if ic_lon is not None:
        ic_y = cy + (g.r_outer + g.angle_off_tb) * math.sin(
            math.radians(_phi(float(ic_lon), asc_lon)))
        region_top = ic_y + g.angle_label_pt * 0.5
    else:
        region_top = g.size + g.pad
    canvas_bottom = g.size + g.pad + g.legend_h
    box_y = region_top + ((canvas_bottom - region_top) - box_h) / 2.0

    parts: list[str] = []
    parts.append(
        f'<rect x="{_fmt(box_x)}" y="{_fmt(box_y)}" width="{_fmt(box_w)}" '
        f'height="{_fmt(box_h)}" rx="8" fill="{_hex(c.bg)}" '
        f'stroke="{_hex(c.cusp)}" stroke-width="1.2"/>'
    )
    parts.append(_text(box_x + bp, box_y + bp + 10, "Glyphs", size=16,
                       color=c.label, anchor="start", weight="bold"))
    y0 = box_y + bp + header_h
    for i, nm in enumerate(items):
        col, row = i % cols, i // cols
        x0 = box_x + bp + col * cw
        y = y0 + row * rh + rh / 2.0
        parts.append(_glyph(nm, x0 + g.legend_glyph * 0.5, y, g.legend_glyph, c.ink))
        parts.append(_text(x0 + g.legend_glyph + 12, y, nm, size=g.legend_pt,
                           color=c.label, anchor="start"))
    return parts
