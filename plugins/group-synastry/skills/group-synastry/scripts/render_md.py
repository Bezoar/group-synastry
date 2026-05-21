"""Markdown rendering for natal / synastry / composite charts."""
from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Optional

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import formatting  # type: ignore[import-not-found]
    import chart as chart_mod  # type: ignore[import-not-found]
    import synastry as synastry_mod  # type: ignore[import-not-found]
    import composite as composite_mod  # type: ignore[import-not-found]
else:
    from .lib import formatting
    from . import chart as chart_mod
    from . import synastry as synastry_mod
    from . import composite as composite_mod


def render_interpretation(interpretation: Optional[dict]) -> str:
    """Render an interpretation block (``{"sections": [...]}``) as markdown.

    Returns an empty string if *interpretation* is falsy or has no sections.
    Section bodies are already markdown, so they're emitted verbatim.
    """
    if not interpretation:
        return ""
    sections = interpretation.get("sections") or []
    if not sections:
        return ""
    out: list[str] = ["", "## Interpretation", ""]
    for section in sections:
        heading = (section.get("heading") or "").strip()
        body = (section.get("body") or "").strip("\n")
        if heading:
            out.append(f"### {heading}")
            out.append("")
        if body:
            out.append(body)
            out.append("")
    return "\n".join(out)


def _planet_row(p: chart_mod.PlanetEntry) -> str:
    glyph = formatting.PLANET_GLYPHS.get(p.name, "")
    sign_glyph = formatting.GLYPHS.get(p.sign, "")
    pos = f"{p.degree}° {sign_glyph} {p.sign} {p.minute:02d}'"
    if p.retrograde:
        pos += " R"
    house = f"{p.house}" if p.house else "—"
    src = "" if p.source == "swisseph" else " *"
    return f"| {glyph} {p.name}{src} | {pos} | {house} |"


def render_natal(chart: chart_mod.NatalChart) -> str:
    lines: list[str] = []
    name = chart.display_name
    lines.append(f"# {name} — Western Tropical Natal Chart")
    lines.append("")
    b = chart.birth
    place = b.get("place_label") or f"{b['lat']:.4f}, {b['lon']:.4f}"
    lines.append(f"**Born:** {b['date']} {b['time']} ({b['tz']}) — {place}")
    lines.append(f"**UT:** {chart.ut_iso}  ·  **JD (UT):** {chart.julian_day_ut:.4f}")
    lines.append(f"**Zodiac:** tropical  ·  **House system:** {chart.house_system}")
    lines.append("")

    if chart.angles:
        lines.append("## Angles")
        lines.append("")
        lines.append("| Angle | Position |")
        lines.append("|---|---|")
        for a in chart.angles:
            sign_glyph = formatting.GLYPHS.get(a.sign, "")
            lines.append(f"| {a.name} | {a.degree}° {sign_glyph} {a.sign} {a.minute:02d}' |")
        lines.append("")

    lines.append("## Planets and Points")
    lines.append("")
    lines.append("| Body | Position | House |")
    lines.append("|---|---|---|")
    for p in chart.planets:
        lines.append(_planet_row(p))
    lines.append("")

    if any(p.source == "keplerian" for p in chart.planets):
        lines.append(
            "\\* Computed via bundled Keplerian elements (Swiss Ephemeris asteroid "
            "file unavailable). Accuracy: ±arcminutes for Ceres/Eris; **±1–2° for "
            "Chiron** because Saturn perturbations preclude better single-element-set "
            "fits over multi-decade ranges. For arcminute Chiron precision, install "
            "`seas_18.se1` from astro.com (see skill/README.md)."
        )
        lines.append("")

    if chart.aspects:
        lines.append("## Notable Aspects")
        lines.append("")
        lines.append("| A | Aspect | B | Orb |")
        lines.append("|---|---|---|---|")
        # Cap to top 25 tightest to keep the report readable.
        for asp in chart.aspects[:25]:
            lines.append(f"| {asp.a} | {asp.aspect} | {asp.b} | {formatting.format_orb(asp.orb_deg)} |")
        lines.append("")

    if chart.notes:
        lines.append("## Notes")
        lines.append("")
        for n in chart.notes:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines)


def render_synastry(report: synastry_mod.SynastryReport) -> str:
    lines: list[str] = []
    lines.append(f"# Synastry — {report.person_a} × {report.person_b}")
    lines.append("")
    lines.append("Western tropical inter-aspects + house overlays in both directions, "
                 "including Chiron, Ceres, Lilith, Eris (per spec D6).")
    lines.append("")

    # Brief natal summary
    for label, ch in (("A: " + report.person_a, report.chart_a),
                      ("B: " + report.person_b, report.chart_b)):
        lines.append(f"## {label}")
        lines.append("")
        lines.append("| Body | Position |")
        lines.append("|---|---|")
        for p in ch["planets"]:
            sign_glyph = formatting.GLYPHS.get(p["sign"], "")
            pos = f"{p['degree']}° {sign_glyph} {p['sign']} {p['minute']:02d}'"
            if p["retrograde"]:
                pos += " R"
            lines.append(f"| {p['name']} | {pos} |")
        if ch["angles"]:
            for a in ch["angles"]:
                if a["name"] in ("Ascendant", "Midheaven"):
                    sign_glyph = formatting.GLYPHS.get(a["sign"], "")
                    lines.append(
                        f"| {a['name']} | {a['degree']}° {sign_glyph} {a['sign']} {a['minute']:02d}' |"
                    )
        lines.append("")

    # Cross-aspects table — top 30 by orb tightness
    lines.append("## Cross-aspects (tightest first)")
    lines.append("")
    lines.append(f"| {report.person_a} | Aspect | {report.person_b} | Orb |")
    lines.append("|---|---|---|---|")
    for asp in report.aspects[:30]:
        lines.append(f"| {asp.a_body} | {asp.aspect} | {asp.b_body} | {formatting.format_orb(asp.orb_deg)} |")
    lines.append("")

    # House overlays
    if report.overlays_a_in_b:
        lines.append(f"## {report.person_a}'s planets in {report.person_b}'s houses")
        lines.append("")
        lines.append("| Body | House |")
        lines.append("|---|---|")
        for o in report.overlays_a_in_b:
            lines.append(f"| {o.body} | {o.house} |")
        lines.append("")

    if report.overlays_b_in_a:
        lines.append(f"## {report.person_b}'s planets in {report.person_a}'s houses")
        lines.append("")
        lines.append("| Body | House |")
        lines.append("|---|---|")
        for o in report.overlays_b_in_a:
            lines.append(f"| {o.body} | {o.house} |")
        lines.append("")

    return "\n".join(lines)


def render_composite(comp: composite_mod.CompositeChart) -> str:
    lines: list[str] = []
    title = "Davison" if comp.method == "davison" else "Midpoint Composite"
    lines.append(f"# {title} — {comp.person_a} & {comp.person_b}")
    lines.append("")
    if comp.method == "davison" and comp.moment:
        m = comp.moment
        lines.append(
            f"Cast for the temporal/spatial midpoint: **{m['ut_datetime']}** "
            f"at lat {m['lat']:.2f}°, lon {m['lon']:.2f}°."
        )
    else:
        lines.append("Per-pair shorter-arc midpoints; equal-house from composite Ascendant.")
    lines.append("")

    if comp.angles:
        lines.append("## Angles")
        lines.append("")
        lines.append("| Angle | Position |")
        lines.append("|---|---|")
        for a in comp.angles:
            sign_glyph = formatting.GLYPHS.get(a.sign, "")
            lines.append(f"| {a.name} | {a.degree}° {sign_glyph} {a.sign} {a.minute:02d}' |")
        lines.append("")

    lines.append("## Bodies")
    lines.append("")
    lines.append("| Body | Position | House |")
    lines.append("|---|---|---|")
    for p in comp.points:
        sign_glyph = formatting.GLYPHS.get(p.sign, "")
        pos = f"{p.degree}° {sign_glyph} {p.sign} {p.minute:02d}'"
        house = f"{p.house}" if p.house else "—"
        lines.append(f"| {p.name} | {pos} | {house} |")
    lines.append("")

    if comp.aspects:
        lines.append("## Internal Aspects (tightest first)")
        lines.append("")
        lines.append("| A | Aspect | B | Orb |")
        lines.append("|---|---|---|---|")
        for asp in comp.aspects[:20]:
            lines.append(f"| {asp.a} | {asp.aspect} | {asp.b} | {formatting.format_orb(asp.orb_deg)} |")
        lines.append("")

    if comp.notes:
        lines.append("## Notes")
        lines.append("")
        for n in comp.notes:
            lines.append(f"- {n}")
        lines.append("")
    return "\n".join(lines)
