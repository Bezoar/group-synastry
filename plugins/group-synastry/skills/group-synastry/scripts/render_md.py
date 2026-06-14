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


# Per-source accuracy of the positions shown. Bodies use a strict best-source
# policy (lib/ephem.py); the figures are each source's documented precision.
# Charts print arc-seconds, so this tells the reader how far to trust them.
ACCURACY_NOTE = (
    "Positions are shown to the arc-second. By source: Sun, planets, lunar "
    "nodes and Lilith — Swiss Ephemeris (Moshier), better than 1″ (Moon ≈3″); "
    "Chiron and Ceres — bundled `seas_18`, ≈ arc-second; Eris — Keplerian "
    "elements (marked \\* where sources are shown), reliable to the arc-minute "
    "only, so its arc-seconds are not significant."
)

# Closing disclaimer for any report that carries prose interpretation. Mirrored
# in lib/render_docx.js (INTERPRETATION_DISCLAIMER) for the .docx/.pdf path.
INTERPRETATION_DISCLAIMER = (
    "Automated interpretation is not a substitute for human intuition. "
    "For entertainment purposes only."
)


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
    # Closing disclaimer (Markdown can't centre; emitted italic).
    out.append(f"_{INTERPRETATION_DISCLAIMER}_")
    out.append("")
    return "\n".join(out)


def _chart_header(natal, title: str, system_line: str) -> list[str]:
    """The shared Markdown header (title + born + UT/JD + a system line) used by
    the natal / medieval / Hellenistic renderers."""
    b = natal.birth
    place = b.get("place_label") or f"{b['lat']:.4f}, {b['lon']:.4f}"
    return [
        f"# {natal.display_name} — {title}",
        "",
        f"**Born:** {b['date']} {b['time']} ({b['tz']}) — {place}",
        f"**UT:** {natal.ut_iso}  ·  **JD (UT):** {natal.julian_day_ut:.4f}",
        system_line,
        "",
    ]


def _angles_table(angles) -> list[str]:
    """A Markdown '## Angles' table for angle entries exposing .name/.longitude."""
    out = ["## Angles", "", "| Angle | Position |", "|---|---|"]
    for a in angles:
        out.append(f"| {a.name} | {formatting.format_position_glyph(a.longitude)} |")
    out.append("")
    return out


def _planet_row(p: chart_mod.PlanetEntry) -> str:
    glyph = formatting.PLANET_GLYPHS.get(p.name, "")
    pos = formatting.format_position_glyph(p.longitude, p.retrograde)
    house = f"{p.house}" if p.house else "—"
    # Flag only bodies computed via the Keplerian fallback (lower accuracy);
    # the source codes are the specific ones from lib/ephem (swisseph_builtin /
    # swisseph_with_seas18 / keplerian_jpl_j2000), so test the prefix.
    src = " *" if p.source.startswith("keplerian") else ""
    return f"| {glyph} {p.name}{src} | {pos} | {house} |"


def render_natal(chart: chart_mod.NatalChart) -> str:
    lines: list[str] = []
    lines += _chart_header(
        chart, "Western Tropical Natal Chart",
        f"**Zodiac:** tropical  ·  **House system:** {chart.house_system}",
    )
    if chart.angles:
        lines += _angles_table(chart.angles)

    lines.append("## Planets and Points")
    lines.append("")
    lines.append("| Body | Position | House |")
    lines.append("|---|---|---|")
    for p in chart.planets:
        lines.append(_planet_row(p))
    lines.append("")

    lines.append(f"_{ACCURACY_NOTE}_")
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
            pos = formatting.format_position_glyph(p["longitude"], p["retrograde"])
            lines.append(f"| {p['name']} | {pos} |")
        if ch["angles"]:
            for a in ch["angles"]:
                if a["name"] in ("Ascendant", "Midheaven"):
                    lines.append(
                        f"| {a['name']} | {formatting.format_position_glyph(a['longitude'])} |"
                    )
        lines.append("")

    lines.append(f"_{ACCURACY_NOTE}_")
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
        lines += _angles_table(comp.angles)

    lines.append("## Bodies")
    lines.append("")
    lines.append("| Body | Position | House |")
    lines.append("|---|---|---|")
    for p in comp.points:
        pos = formatting.format_position_glyph(p.longitude)
        house = f"{p.house}" if p.house else "—"
        lines.append(f"| {p.name} | {pos} | {house} |")
    lines.append("")
    lines.append(f"_{ACCURACY_NOTE}_")
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


def render_medieval(mc) -> str:
    """Render a medieval / traditional chart as Markdown.

    *mc* is a ``lib.medieval.MedievalChart`` (sect, essential dignities, lots,
    almuten layered on the natal computation). Computation only — no
    interpretation prose or citations (those depend on the verified corpus, a
    separate sub-project; see docs/research/biblio.md).
    """
    natal = mc.natal
    lines: list[str] = []
    lines += _chart_header(
        natal, "Medieval / Traditional Chart",
        f"**Zodiac:** tropical  ·  **House system:** {natal.house_system}",
    )

    lines.append("## Sect")
    lines.append("")
    lines.append(f"- **Chart sect:** {mc.sect}")
    lines.append(f"- **Sect light:** {mc.sect_light}")
    lines.append(f"- **Benefic of the sect:** {mc.benefic_of_sect}")
    lines.append(
        f"- **Malefic of the sect:** {mc.malefic_of_sect}  ·  "
        f"**Contrary (out-of-sect) malefic:** {mc.contrary_malefic}"
    )
    lines.append("")

    if natal.angles:
        lines += _angles_table(natal.angles)

    pos_by_name = {p.name: p for p in natal.planets}
    lines.append("## Essential Dignities")
    lines.append("")
    lines.append("| Body | Position | Dignities | Score | Debility |")
    lines.append("|---|---|---|---|---|")
    for d in mc.dignities:
        p = pos_by_name.get(d.planet)
        glyph = formatting.PLANET_GLYPHS.get(d.planet, "")
        pos = formatting.format_position_glyph(p.longitude, p.retrograde) if p else "—"
        dign = ", ".join(d.dignities) if d.dignities else ("peregrine" if d.peregrine else "—")
        score = f"+{d.score}" if d.score else "0"
        debils = [x for x in ("detriment", "fall") if getattr(d, x)]
        lines.append(
            f"| {glyph} {d.planet} | {pos} | {dign} | {score} | "
            f"{', '.join(debils) if debils else '—'} |"
        )
    lines.append("")
    lines.append(
        "_Scoring: domicile +5, exaltation +4, triplicity +3, term +2, face +1. "
        "Egyptian terms, Dorothean triplicities, Chaldean faces._"
    )
    lines.append("")

    alm = mc.almuten_asc
    ranked = ", ".join(
        f"{pl} {sc}" for pl, sc in sorted(alm.scores.items(), key=lambda kv: -kv[1])
    )
    lines.append("## Almuten of the Ascendant")
    lines.append("")
    lines.append(f"- **Almuten:** {alm.winner}")
    lines.append(f"- **Dignity scores over the degree:** {ranked}")
    lines.append("")

    lines.append("## Lots")
    lines.append("")
    lines.append("| Lot | Position |")
    lines.append("|---|---|")
    for lot_name, lot_lon in mc.lots.items():
        lines.append(f"| Lot of {lot_name} | {formatting.format_position_glyph(lot_lon)} |")
    lines.append("")

    lines.append("## Antiscia")
    lines.append("")
    lines.append("| Body | Antiscion | Contra-antiscion |")
    lines.append("|---|---|---|")
    for a in mc.antiscia:
        glyph = formatting.PLANET_GLYPHS.get(a.planet, "")
        lines.append(
            f"| {glyph} {a.planet} | {formatting.format_position_glyph(a.antiscion)} "
            f"| {formatting.format_position_glyph(a.contra_antiscion)} |"
        )
    lines.append("")
    if mc.antiscia_contacts:
        for c in mc.antiscia_contacts:
            lines.append(f"- **{c.b}** falls on **{c.a}**'s {c.kind} (orb {c.orb:.2f}°)")
        lines.append("")

    lines.append("## Mutual Reception")
    lines.append("")
    if mc.mutual_receptions:
        for m in mc.mutual_receptions:
            lines.append(
                f"- **{m.a}** ↔ **{m.b}** — {m.a} receives {m.b} by "
                f"{', '.join(m.a_receives_b)}; {m.b} receives {m.a} by "
                f"{', '.join(m.b_receives_a)}"
            )
    else:
        lines.append("- None (by domicile or exaltation).")
    lines.append("")

    lines.append(f"_{ACCURACY_NOTE}_")
    lines.append("")
    return "\n".join(lines)


def render_profection(natal, rep) -> str:
    """Render an annual profection as Markdown.

    *rep* is a ``lib.medieval.ProfectionReport``. Predictive — surfaced only on
    explicit request. Computation only (no interpretation prose or citations).
    """
    p = rep.profection
    lines: list[str] = []
    lines.append(f"# {natal.display_name} — Annual Profection (age {p.age})")
    lines.append("")
    lines.append(
        f"- **Profected house:** {p.profected_house}  ·  "
        f"**Profected sign:** {p.profected_sign}"
    )
    lines.append(f"- **Lord of the Year:** {p.lord_of_year}")
    lines.append("")

    lines.append("## Lord of the Year — natal condition")
    lines.append("")
    d = rep.lord_dignities
    house = f"house {rep.lord_house}" if rep.lord_house else "house —"
    dign = ", ".join(d.dignities) if d.dignities else ("peregrine" if d.peregrine else "—")
    score = f"+{d.score}" if d.score else "0"
    debils = [x for x in ("detriment", "fall") if getattr(d, x)]
    lines.append(
        f"- **{p.lord_of_year}** at {formatting.format_position_glyph(rep.lord_longitude)} "
        f"({house})"
    )
    debil_str = f"  ·  **Debility:** {', '.join(debils)}" if debils else ""
    lines.append(f"- **Dignities:** {dign}  ·  **Score:** {score}{debil_str}")
    lines.append("")
    lines.append(
        "_Annual profection: one sign per completed year from the natal Ascendant "
        "(age 0 = 1st house), on a 12-year cycle; the lord of the year is the "
        "domicile ruler of the profected sign. Predictive — computed only on "
        "explicit request._"
    )
    lines.append("")
    return "\n".join(lines)


def render_hellenistic(hc) -> str:
    """Render a Hellenistic natal chart as Markdown.

    *hc* is a ``lib.hellenistic.HellenisticChart`` (Whole-Sign houses, sect, lots,
    triplicity lords of the sect light). Computation only — no prose/citations.
    """
    natal = hc.natal
    lines: list[str] = []
    lines += _chart_header(
        natal, "Hellenistic Natal Chart",
        "**Zodiac:** tropical  ·  **Houses:** Whole-Sign",
    )

    lines.append("## Sect")
    lines.append("")
    lines.append(f"- **Chart sect:** {hc.sect}  ·  **Sect light:** {hc.sect_light}")
    lines.append(
        f"- **Benefic of the sect:** {hc.benefic_of_sect}  ·  "
        f"**Malefic of the sect:** {hc.malefic_of_sect}  ·  "
        f"**Contrary malefic:** {hc.contrary_malefic}"
    )
    lines.append("")

    lines.append("## Whole-Sign Houses")
    lines.append("")
    lines.append("| Body | Position | House | Place |")
    lines.append("|---|---|---|---|")
    for w in hc.whole_sign_houses:
        glyph = formatting.PLANET_GLYPHS.get(w.planet, "")
        lines.append(
            f"| {glyph} {w.planet} | {formatting.format_position_glyph(w.longitude)} "
            f"| {w.house} | {w.category} |"
        )
    lines.append("")

    lines.append("## Lots")
    lines.append("")
    lines.append("| Lot | Position | House |")
    lines.append("|---|---|---|")
    for name, lon in hc.lots.items():
        lines.append(
            f"| Lot of {name} | {formatting.format_position_glyph(lon)} "
            f"| {hc.lot_houses.get(name, '—')} |"
        )
    lines.append("")

    lines.append("## Triplicity Lords of the Sect Light")
    lines.append("")
    lines.append(
        f"Sect light **{hc.sect_light}** — triplicity lords, in order: "
        f"{', '.join(hc.triplicity_lords_of_sect_light)}."
    )
    lines.append("")

    lines.append(f"_{ACCURACY_NOTE}_")
    lines.append("")
    return "\n".join(lines)


def render_vedic(vc) -> str:
    """Render a Vedic (sidereal) natal chart as Markdown.

    *vc* is a ``lib.vedic.VedicChart`` (sidereal grahas, nakshatras, Whole-Sign
    rasi houses). Computation only — no prose; no dasha timeline / Navamsa yet.
    """
    natal = vc.natal
    lines: list[str] = []
    lines += _chart_header(
        natal, "Vedic (Sidereal) Chart",
        f"**Zodiac:** sidereal ({vc.ayanamsa_mode}, ayanamsa {vc.ayanamsa_value:.4f}°)"
        "  ·  **Houses:** Whole-Sign (rasi)",
    )

    a = vc.ascendant
    lines.append("## Ascendant (Lagna)")
    lines.append("")
    lines.append(f"- **Lagna:** {formatting.format_position_glyph(a.longitude)}")
    lines.append(f"- **Nakshatra:** {a.nakshatra} (pada {a.pada})")
    lines.append("")

    lines.append("## Grahas (Sidereal)")
    lines.append("")
    lines.append("| Graha | Sidereal Position | Rasi House | Nakshatra (pada) | Lord |")
    lines.append("|---|---|---|---|---|")
    for g in vc.grahas:
        glyph = formatting.PLANET_GLYPHS.get(g.name, "")
        pos = formatting.format_position_glyph(g.sidereal_longitude, g.retrograde)
        lines.append(
            f"| {glyph} {g.name} | {pos} | {g.rasi_house} "
            f"| {g.nakshatra} ({g.pada}) | {g.lord} |"
        )
    lines.append("")

    mn = vc.moon_nakshatra
    lines.append(
        f"**Janma (birth) nakshatra:** {mn.name}, pada {mn.pada} — Vimshottari lord {mn.lord}."
    )
    lines.append("")
    lines.append(
        f"_{ACCURACY_NOTE} Sidereal longitudes are tropical − ayanamsa ({vc.ayanamsa_mode}); "
        "the Vimshottari dasha timeline and the Navamsa (D9) are not yet computed._"
    )
    lines.append("")
    return "\n".join(lines)
