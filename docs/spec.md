# `group-synastry` — Skill Specification

> **⚠ Historical document.** This is the **original Phase 1 design spec**,
> kept for historical context. The repository has moved on — Phase 2 (.docx /
> .pdf rendering, themes, default output dir) and Phase 1.5 (LLM-authored
> interpretation with sidecar persistence) are now built. For the
> authoritative description of the repository as it stands today, see
> **[`docs/specs/primary.md`](specs/primary.md)**. The decisions D1–D9
> listed below are still valid for v1 scope, but implementation paths and
> file locations have changed; consult the primary spec for current truth.

**Status:** Draft v1.0
**Author origin:** Distilled from a Claude.ai design conversation, May 2026
**Target environments:** Claude Code (primary) and Claude.ai (fully supported)
**Implementation target:** Hand-off to Claude Code

---

## 1. Overview

`group-synastry` is a Claude skill that maintains a small private database of people's birth data and produces:

1. **Detailed individual birth charts** in any of several astrological systems
2. **Synastry charts** (inter-aspects + house overlays) for any pair of people in the group
3. **Composite charts** (midpoint + Davison) for any pair, where applicable
4. **Predictive analyses** (progressions, transits, returns, dashas, etc.) for individuals

Output formats: inline Markdown, `.docx`, `.pdf`. The user picks-and-chooses which charts/systems to compute on each invocation — there is no monolithic "do everything" report.

The skill is designed to live primarily in Claude Code at `~/.claude/skills/group-synastry/`, but the same skill bundle works uploaded to Claude.ai. The only thing that differs between environments is the location of the people-database file (see §5).

---

## 2. Decision Log

The following choices have been made and frozen for v1:

| # | Decision | Choice |
|---|---|---|
| D1 | Primary environment | Both Claude Code and Claude.ai |
| D2 | Predictive scope in v1 | Full toolkit; pick-and-choose at invocation |
| D3 | Database storage | JSON file at `~/.config/group-synastry/people.json` (Claude Code); upload/download workflow on Claude.ai |
| D4 | Default house system | Placidus (configurable per call) |
| D5 | Default Vedic ayanamsa | Lahiri (configurable per call) |
| D6 | Always-included bodies in synastry | Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Lilith (Mean Apogee), Ceres, Eris, True Node, ASC, MC |
| D7 | Time zone authority | IANA tz database (Python `zoneinfo`) — handles historical DST quirks |
| D8 | Geocoding | Manual lat/lon entry by default; Claude can suggest coords via web search if available |
| D9 | Privacy | Plain-text JSON, no encryption in v1; document this for the user |

---

## 3. Goals & Non-Goals

### Goals
- Accurate computation of planetary positions using Swiss Ephemeris for any date 1800–2100
- Multi-system support: Western tropical, Vedic, Hellenistic, Chinese BaZi, Draconic, Heliocentric
- Support for non-default bodies — **Chiron, Ceres, Pallas, Juno, Vesta, Eris**, and other centaurs/TNOs (Pholus, Nessus, Sedna, Haumea, Makemake) — via bundled JPL Keplerian orbital elements as fallback when Swiss Ephemeris asteroid files are unavailable. **Lilith (Mean Black Moon Apogee)** is computed natively by Swiss Ephemeris as a mathematical sensitive point (no ephemeris file or Keplerian fallback needed)
- Polished output: clean Markdown, professional `.docx`, typeset `.pdf`
- Group operations: pairwise synastry/composite over any two people in the database
- Idempotent, scriptable invocation — Claude Code should be able to fire individual computations without invoking everything

### Non-Goals (v1)
- Real-time astrology (live updating charts)
- Mundane astrology (charts for events/cities)
- Horary (question charts)
- Electional (best-time-for-X charts)
- Astrocartography / locational (deferred to v2)
- Web UI / GUI
- Multi-user authentication, sharing, or sync
- Cloud storage of birth data

---

## 4. User Stories

These are the canonical phrases the skill should trigger on. Keep this list synchronized with the eval set.

### People management
- "Add Alex to my group: born June 15, 1988 at 8:20 AM in Chicago, Illinois (41.88° N, 87.63° W, CDT)"
- "Add Jordan: Feb 9, 1991, 2:45 PM, Denver OH"
- "Show me everyone in the group"
- "Update Alex's birth time to 1:46 PM"
- "Remove the entry for [X]"
- "Tag Alex and Jordan as 'family'"

### Individual charts
- "Show me Alex's full Western chart"
- "Compute Alex's Vedic chart"
- "Make a Chinese BaZi reading for Jordan"
- "Give me Alex's Hellenistic Lots"
- "What are Jordan's declinations?"

### Synastry / composite
- "Synastry between Alex and Jordan"
- "Composite chart for Alex and Jordan"
- "Davison chart for Alex and Jordan"
- "Make a Word doc of the synastry between Alex and Jordan"
- "Make a PDF of the composite for Alex and Jordan"

### Predictive (individual)
- "Run a progression reading for Alex for today"
- "What's Alex's current Vedic dasha?"
- "Solar Return for Jordan 2026"
- "Current transits to Alex's natal chart"

### Group operations
- "Compatibility matrix for everyone in the group"
- "Synastry between Alex and everyone else"

### Selectivity (always)
The user MUST be able to specify *which* systems and *which* output format they want. Default to inline Markdown unless the user asks for `.docx` or `.pdf`.

---

## 5. Architecture

### 5.1 File Layout

```
group-synastry/
├── SKILL.md                          # main triggering doc (~400 lines max)
├── scripts/
│   ├── db.py                         # people.json CRUD
│   ├── chart.py                      # main individual-chart engine
│   ├── synastry.py                   # pairwise synastry
│   ├── composite.py                  # midpoint + Davison
│   ├── progressions.py               # secondary progressions, solar arc
│   ├── transits.py                   # transits to natal
│   ├── returns.py                    # solar/lunar returns
│   ├── vedic.py                      # sidereal, nakshatras, dashas
│   ├── chinese.py                    # BaZi pillars + Da Yun
│   ├── hellenistic.py                # Lots, profections, ZR
│   ├── render_md.py                  # → markdown report
│   ├── render_docx.py                # → .docx (uses Node + docx lib)
│   ├── render_pdf.py                 # → .pdf (via LibreOffice)
│   ├── group_ops.py                  # compatibility matrix, batch ops
│   └── lib/
│       ├── ephem.py                  # Swiss Eph wrapper + fallbacks
│       ├── orbital_elements.py       # JPL elements for non-Swiss bodies (Eris, Chiron, Ceres, Pallas, Juno, Vesta, Sedna...)
│       ├── kepler.py                 # Keplerian solver + heliocentric→geocentric
│       ├── tz.py                     # IANA tz handling + historical DST
│       ├── geocode.py                # optional place lookup helpers
│       ├── env.py                    # detect Claude Code vs Claude.ai context
│       └── formatting.py             # degree/sign/orb formatters
├── references/                       # loaded into context only when relevant
│   ├── western-tropical.md           # aspect interpretation, house meanings
│   ├── vedic.md                      # nakshatras, dasha rules, kuta matching
│   ├── chinese.md                    # 10 stems, 12 branches, 5 phases, BaZi rules
│   ├── hellenistic.md                # Lots formulas, profection rules, ZR algorithm
│   ├── synastry-aspects.md           # orb tables, synastry interpretation snippets
│   ├── asteroids-and-points.md       # interpretation of Chiron, Eris, Lilith, Ceres, Vesta, etc.
│   └── interpretation-glossary.md    # short generic glossary
├── assets/
│   ├── docx-template.json            # design tokens (colors, fonts) for DOCX
│   └── ephe/                         # bundled Swiss Eph files (small subset; main planet files only — too large to bundle asteroid files)
├── tests/
│   ├── test_chart.py                 # known-good positions for fixed dates
│   ├── test_synastry.py
│   ├── test_composite.py
│   ├── test_predictive.py
│   └── fixtures/
│       └── reference_charts.json     # validated chart positions to test against
└── README.md                          # human-facing docs
```

### 5.2 Database Location

`scripts/lib/env.py` exposes a `data_dir()` function that returns the right path:

| Environment | Detection | DB path |
|---|---|---|
| Claude Code | `os.environ.get("CLAUDE_CODE")` or absence of `/mnt/user-data/` | `~/.config/group-synastry/people.json` (created on first use; respects `XDG_CONFIG_HOME`) |
| Claude.ai (web/desktop) | Presence of `/mnt/user-data/uploads/` and `/mnt/user-data/outputs/` | Looks for uploaded `people.json` in `/mnt/user-data/uploads/`; writes updates to `/mnt/user-data/outputs/people.json` for the user to download |

In Claude.ai mode, when the user says "add Alex to my group" without having uploaded a `people.json`, the skill creates one fresh in `/mnt/user-data/outputs/` and tells the user to save it locally and re-upload it next time. This is documented in `README.md` and `SKILL.md`.

### 5.3 Output Location

Always write output files to:
- Claude Code: current working directory unless user specifies otherwise
- Claude.ai: `/mnt/user-data/outputs/`

Filenames follow `<kind>-<names>-<YYYYMMDD>.{md,docx,pdf}` — e.g. `synastry-alex-jordan-20260504.docx`.

---

## 6. Data Model

### 6.1 `people.json` Schema

```json
{
  "version": 1,
  "updated_at": "2026-05-04T12:00:00Z",
  "people": [
    {
      "id": "alex",
      "display_name": "Alex",
      "birth": {
        "date": "1988-06-15",
        "time": "08:20",
        "tz": "America/Chicago",
        "lat": 41.8781,
        "lon": -87.6298,
        "place_label": "Chicago, IL",
        "time_accuracy": "exact",
        "notes": "Birth location confirmed."
      },
      "tags": ["spouse", "family"],
      "added_at": "2026-05-04T20:14:00Z"
    },
    {
      "id": "jordan",
      "display_name": "Jordan",
      "birth": {
        "date": "1991-02-09",
        "time": "14:45",
        "tz": "America/Denver",
        "lat": 39.7392,
        "lon": -104.9903,
        "place_label": "Denver, CO",
        "time_accuracy": "exact"
      },
      "tags": ["spouse", "family"]
    }
  ]
}
```

Field rules:
- `id`: lowercase, ASCII, unique within the file. Auto-generated from `display_name` if not given.
- `tz`: must be a valid IANA name. The skill will reject `"EDT"`, `"PST"`, etc. and ask for the IANA equivalent.
- `lat`, `lon`: signed decimals. North/East positive, South/West negative.
- `time_accuracy`: one of `exact`, `approximate`, `noon-default`, `unknown`. Charts requiring time (Ascendant, houses) will warn or refuse if accuracy is `unknown`.

### 6.2 `settings.json` (optional)

User-overridable defaults:

```json
{
  "default_house_system": "placidus",
  "default_ayanamsa": "lahiri",
  "default_orbs": {
    "conjunction": 8, "opposition": 8, "trine": 7, "square": 7,
    "sextile": 5, "quincunx": 3, "semisextile": 2,
    "semisquare": 2, "sesquisquare": 2
  },
  "tighter_orbs_for_minor_bodies": 3,
  "tighter_orbs_for_angles": 5,
  "default_output_format": "markdown"
}
```

---

## 7. Astrological Systems Supported

| System | Individual chart | Synastry | Composite (midpoint) | Davison |
|---|---|---|---|---|
| Western tropical (Placidus / Whole-Sign / Equal / Koch) | ✓ | ✓ | ✓ | ✓ |
| Vedic / Jyotish (sidereal, multi-ayanamsa) | ✓ | ✓ (kuta-style + inter-aspects) | ✗ (not traditional) | ✗ |
| Hellenistic (Whole-Sign, Lots, sect) | ✓ | ✓ (alongside tropical) | rarely meaningful | ✗ |
| Chinese BaZi (Four Pillars) | ✓ | ✓ (element compat, animal triads) | ✗ | ✗ |
| Draconic | ✓ | ✓ (alongside tropical) | ✓ | ✓ |
| Heliocentric | ✓ | rarely used | rarely used | ✗ |

Predictive systems (individual only):
- Secondary progressions (Western)
- Solar arc directions (Western)
- Solar Return / Lunar Return (Western)
- Current transits to natal (Western)
- Annual profections (Hellenistic)
- Vimshottari Dasha (Vedic — Mahadasha, Antardasha, Pratyantardasha)
- Zodiacal Releasing from Spirit & Fortune (Hellenistic)
- Chinese Da Yun (10-year luck pillars)

---

## 8. Bodies, Points, and Sensitive Degrees

### Always computed (every individual chart)
Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, **Chiron**, **Ceres**, **Eris**, True Node (with derived South Node), **Mean Lilith (Black Moon Apogee)**, Ascendant, MC, Descendant, IC, Vertex.

This always-computed list aligns with D6 — the same bodies are guaranteed available for synastry and composite work. Chiron, Ceres, and Eris use the bundled Keplerian fallback if Swiss Ephemeris asteroid files aren't present; Lilith is a mathematical apogee point computed natively by Swiss Ephemeris (no fallback needed).

### Computed on user request
- **Centaurs**: Pholus, Nessus, Chariklo (Chiron is in the always-computed set)
- **Asteroids**: Pallas, Juno, Vesta (Ceres is in the always-computed set)
- **TNOs / dwarf planets**: Sedna, Haumea, Makemake, Quaoar, Orcus (Eris is in the always-computed set)
- **Other Liliths**: Asteroid Lilith (#1181), Dark Moon Lilith (Waldemath), True/Osculating Lilith (the Mean Lilith in the always-computed set is the most commonly used; the others are computed on request)
- **Fixed stars**: configurable list; default to the 17 most-used (Algol, Alcyone, Aldebaran, Rigel, Bellatrix, Betelgeuse, Sirius, Castor, Pollux, Procyon, Regulus, Spica, Arcturus, Antares, Vega, Altair, Fomalhaut)
- **Arabic Parts / Hellenistic Lots**: Fortune, Spirit, Eros, Necessity, Courage, Victory, Nemesis, Marriage, Children, Father, Mother, plus user-defined custom Lots
- **Midpoints**: configurable list; default selection includes Sun/Moon, Sun/Venus, Venus/Mars, Sun/Saturn, ASC/MC

### Always computed for synastry & composite (per D6)
Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Lilith, Ceres, Eris, True Node, ASC, MC.

### Body computation source

Use Swiss Ephemeris (`pyswisseph`) when files are available. For bodies whose ephemeris files (`seas_*.se1`, asteroid-specific files) are not bundled or downloadable, fall back to bundled JPL Keplerian elements via `scripts/lib/orbital_elements.py` and `scripts/lib/kepler.py`.

**Accuracy of the Keplerian fallback:**

- **Ceres, Pallas, Juno, Vesta, Eris:** ±arcminutes over the 1800–2100 range — sufficient for astrology.
- **Chiron:** ±1–2°, *not* arcminutes. Chiron is heavily perturbed by Saturn (its perihelion crosses inside Saturn's orbit), and a single Keplerian element set cannot fit the perturbed orbit better than degree-scale over multi-decade ranges. For arcminute Chiron precision, install the Swiss Ephemeris asteroid file `seas_18.se1` (~250 KB from astro.com); the skill's `lib/ephem.py` wrapper will prefer Swiss Eph automatically when the file is present. Without the file, the chart-output footer notes the Keplerian fallback in use and its accuracy limit.

**Note on Lilith:** The Mean Black Moon (Mean Apogee) used as the always-included "Lilith" is a mathematical sensitive point — the empty focus of the Moon's elliptical orbit — and is computed natively by Swiss Ephemeris (`swe.MEAN_APOG`) without needing any ephemeris file or Keplerian fallback. It does not appear in the orbital-elements dictionary below for that reason. The True/Osculating Lilith (`swe.OSCU_APOG`) is similarly mathematical and built-in. Only **asteroid Lilith** (#1181) — a separate, much rarer object — would require Keplerian fallback, and would be added to the dictionary if computed on request.

Bundled orbital elements (J2000 epoch except Eris):

```python
ELEMENTS = {
    'Ceres':  (a=2.7691651, e=0.0760091, i=10.59407°, Ω=80.30553°, ω=73.59770°, M=95.98905°,  P=4.6041yr),
    'Pallas': (a=2.7728118, e=0.2299838, i=34.83727°, Ω=173.08006°, ω=310.20706°, M=78.21443°, P=4.6125yr),
    'Juno':   (a=2.6685271, e=0.2570425, i=12.99178°, Ω=169.85318°, ω=248.10160°, M=33.16410°, P=4.3623yr),
    'Vesta':  (a=2.3617858, e=0.0886211, i=7.14180°,  Ω=103.85093°, ω=151.19853°, M=169.39812°, P=3.6299yr),
    'Chiron': (a=13.6796,   e=0.38132,   i=6.9255°,   Ω=209.3829°,  ω=339.5193°,  M=348.062°,  P=50.76yr),
    'Eris':   (a=67.78290,  e=0.43607,   i=44.19200°, Ω=35.94975°,  ω=151.66135°, M=205.98961°, P=558.04yr, epoch=JD 2459800.5),
}
```

**Note on Chiron M (corrected 2026-05-07):** Spec v1 carried `M=76.48468°` for Chiron at J2000. Verification against PyEphem (independent Kepler solver) and the JPL Small-Body Database showed that value is the mean anomaly at JD ≈ 2456096 (June 2012), not J2000 — produced when someone copied 2012-era JPL Horizons output and labeled the epoch as J2000 without re-propagating M. The correct J2000 value is `M=348.062°`. The other elements (a, e, i, Ω, ω) drift slowly between epochs and were close enough that the bug was masked.

---

## 9. Skill Behavior — How Claude Should Use This

### 9.1 Triggering

`SKILL.md`'s description should fire on any of: "synastry", "composite chart", "natal chart", "birth chart", "Vedic chart", "BaZi", "progressions", "Solar Return", "transits", "compatibility report", or mention of two named people in the group with relational/astrological framing.

The description should be slightly pushy (per skill-creator guidance) — for example: *"Use this skill whenever the user mentions synastry, composite charts, natal charts, birth chart computation, Vedic readings, BaZi, progressions, transits, or asks about astrological compatibility between two named people. Use it even if the user doesn't explicitly say 'astrology' — phrases like 'how do Alex and Jordan get along astrologically' or 'what's the chart for Aug 1 1962' should trigger this skill."*

### 9.2 Single-shot Invocation Flow

For "synastry between Alex and Jordan":
1. Read `SKILL.md` (always) to load the skill's behavior contract.
2. Look up Alex and Jordan in the database via `db.py`. If either is missing, prompt the user once for their birth data and offer to add them.
3. **Apply the §9.4 Clarification First rule** — ask the user about output format, depth, and any other meaningful choices, unless their request was already specific or settings.json overrides apply.
4. Run `synastry.py` with the two charts.
5. Render with `render_md.py` for inline output (default) or `render_docx.py` / `render_pdf.py` if the user asked for those formats.
6. Present results to the user.

For ambiguous requests like "do Alex's chart": apply §9.4 — ask which system before computing anything.

### 9.3 Pick-and-Choose Behavior (D2)

The skill MUST allow selectivity. When a user requests a "full chart," default to the Western tropical chart only — not all systems. Only run additional systems when explicitly requested. Predictive features are never auto-included.

The exception: when the user invokes a "full reading" or "everything you've got" type phrase, run a comprehensive suite and warn about token/time cost first.

### 9.4 Clarification First — Ask Before Computing

**This is a hard behavioral rule.** The skill must ask the user for clarification before running computations when meaningful choices exist. Defaults exist as final fallbacks for users who say "just go," not as silent assumptions baked into every invocation.

**Always ask about:**
- **Which astrological system(s)** — when the user says "do Alex's chart" without specifying Western / Vedic / Chinese / Hellenistic / etc.
- **Output format** — when producing a substantial deliverable. Options: inline markdown, `.docx`, `.pdf`, or several at once.
- **Target date** — for any predictive request ("progressions", "transits", "Solar Return"). Default offer: today.
- **House system** — for Western charts when not specified. State the default (Placidus) in the question.
- **Ayanamsa** — for Vedic charts when not specified. State the default (Lahiri) in the question.
- **Optional bodies** — for any chart, whether to include fixed stars, Arabic Parts, harmonic charts, or specialized asteroids beyond the always-included set.
- **Depth of interpretation** — quick data-only output vs. comprehensive analysis with interpretive paragraphs.

**Always ask before expensive operations:**
- **Group compatibility matrix** (N×N) — confirm which subset of people, what depth, output format.
- **Multi-system "everything" reading** — list what would be included and confirm before running.
- **Adding a person without all required fields** — confirm tz (must be IANA), lat/lon, and `time_accuracy`.
- **Computing without a known birth time** — confirm the user accepts a chart with disabled angles, houses, and Vertex.

**Don't ask when:**
- The user has already given specifics in the prompt (e.g., "Vedic chart for Alex with Lahiri ayanamsa")
- The operation is conversational and the defaults are obviously appropriate (e.g., "what's Alex's Sun sign?")
- The user has explicit `settings.json` preferences covering the decision (e.g., `default_output_format: "docx"`)
- The user is iterating on a recent result in the same conversation ("now do that as a PDF", "and now for Jordan")

**How to ask:**
- Prefer `ask_user_input_v0` when available (mobile-friendly tappable options).
- Otherwise use a short inline question with numbered options.
- **Never more than 2 questions at once** — pick the most material decision; default the rest with a brief note ("I'll use Placidus and inline markdown unless you say otherwise").
- Always state defaults clearly so the user can say "just use defaults" or "go with whatever."

**Example interaction patterns:**

> **User:** "Do Alex's chart"
> **Claude:** *Asks:* Which system? (Western tropical / Vedic / Chinese BaZi / Hellenistic / all). Default if you say "just go": Western tropical with Placidus houses, inline markdown.

> **User:** "Synastry between Alex and Jordan"
> **Claude:** *Asks:* Output format? (Inline markdown / Word doc / PDF / all three). Will compute the full synastry (cross-aspects + house overlays both directions + asteroid contacts including Chiron, Ceres, Lilith, Eris) unless you want it scoped down.

> **User:** "Run progressions for Alex"
> **Claude:** *Asks:* Target date? (Today / specific date / your next birthday for a Solar Return). Will run secondary progressions + solar arc directions + current major transits by default — say "minimal" for just one of these, or "everything" to also include profections, dasha, and ZR.

> **User:** "Compatibility matrix for everyone"
> **Claude:** *Asks:* For the [N] people in your group, that's [N(N-1)/2] pairs. Depth? (1-line summary per pair / paragraph per pair / full report per pair). Output? (Single combined doc / one file per pair / inline). Confirm before I run.

### 9.5 Disambiguation

If two people in the database share a first name, the skill prompts to disambiguate using IDs, tags, or birth year. IDs in the JSON are the canonical handle; display names are user-friendly.

---

## 10. Output Formats

### 10.1 Markdown (default)
- Clean, well-structured headers (`#`, `##`, `###`)
- Tables for chart positions and aspect lists
- Bulletted highlights for key features
- Inline glyphs for signs/aspects (`☉ Sun`, `♈ Aries`, `☌`, `△`, `□`, `☍`, `⚹`)
- Suitable for direct inline display in a chat

### 10.2 .docx
- Use the docx-js Node library (matches the docx skill's approach)
- Built-in template `assets/docx-template.json` defines colors, fonts, table styling
- Include title page, table of contents (for long reports), section headers, formatted tables, footer with page numbers
- Validate every output with the docx skill's `validate.py` before presenting

### 10.3 .pdf
- Convert from `.docx` via LibreOffice headless (already known to work in both environments)
- Same content, paginated and styled

### 10.4 Style Tokens (centralized)

```json
{
  "fonts": { "body": "Calibri", "heading": "Calibri", "mono": "Consolas" },
  "colors": {
    "title": "#1F2A4A", "heading": "#2E3E68", "subheading": "#3D5285",
    "accent": "#8B6F47", "rule": "#B8B4C8",
    "table_header_bg": "#2E3E68", "table_alt_row_bg": "#F2F0F7"
  },
  "page_size": "letter"
}
```

---

## 11. Phased Implementation Plan

### Phase 1 — Foundation & MVP (Western tropical)
- `lib/env.py`, `lib/tz.py`, `lib/ephem.py`, `lib/kepler.py`, `lib/orbital_elements.py`, `lib/formatting.py`
- `db.py` — full CRUD on `people.json`
- `chart.py` — Western tropical natal chart with all standard bodies + Chiron/Eris/Lilith/Ceres
- `synastry.py` — inter-aspects + house overlays
- `composite.py` — midpoint + Davison
- `render_md.py` — markdown rendering
- `SKILL.md` — initial draft
- Tests for known positions of Sun/Moon/planets at fixed historical dates

### Phase 2 — Output Polish
- `render_docx.py` — Word output via Node + docx-js
- `render_pdf.py` — PDF via LibreOffice headless
- Title pages, footers, table styling
- Validate against docx skill's validator

### Phase 3 — Multi-system
- `vedic.py` — sidereal positions, nakshatras, multi-ayanamsa support
- `hellenistic.py` — Lots, sect detection, Whole-Sign houses
- `chinese.py` — Four Pillars, Five Phases, Day Master analysis

### Phase 4 — Predictive
- `progressions.py` — secondary progressions, solar arc directions
- `transits.py` — current transits to natal, slow-mover focus
- `returns.py` — Solar Return, Lunar Return
- Add Vimshottari Dasha to `vedic.py`
- Add Zodiacal Releasing + Profections to `hellenistic.py`
- Add Da Yun (luck pillars) to `chinese.py`

### Phase 5 — Group Operations
- `group_ops.py` — compatibility matrix (NxN table of compatibility scores)
- Bulk synastry: "everyone vs Alex"
- Group composite (midpoint of N charts) — experimental

### Phase 6 — Polish & Optional
- Fixed star database + conjunction detection
- Asteroid library expansion (Lilith asteroid #1181, Sappho, Eros, Psyche, Karma, etc.)
- Locational astrology / astrocartography
- Harmonic charts

---

## 12. Dependencies

### Python
- `pyswisseph >= 2.10` — Swiss Ephemeris bindings
- Python 3.10+ stdlib: `zoneinfo`, `datetime`, `json`, `math`, `pathlib`
- (Optional) `geopy` — for `geocode.py` if user wants place-name lookups

### Node.js (for `.docx` output)
- `docx@9.x` — installed globally: `npm install -g docx`

### System
- `libreoffice` — headless PDF conversion. Available in Claude.ai sandbox; Claude Code users may need to install.

### Bundled, no install
- JPL orbital elements for centaurs/asteroids/TNOs (in `lib/orbital_elements.py` as Python literals)

### Optional, downloaded on-demand
- Swiss Ephemeris asteroid files (`seas_*.se1`, etc.) — fetched from astro.com if the user requests heavy asteroid work and the files aren't present. Skill should NEVER auto-download without telling the user.

---

## 13. Testing

### Reference fixtures
Maintain `tests/fixtures/reference_charts.json` with a handful of charts whose positions have been validated against astro.com or Solar Fire. At least:
- A modern chart (e.g., 2000-01-01 Greenwich)
- A historical chart spanning DST quirks (e.g., 1988-06-15 Chicago OH — this conversation's case)
- A pre-1900 chart (e.g., 1850-06-15 London) to test long-range accuracy
- Southern hemisphere chart (e.g., 1980-12-25 Sydney)
- Chart at the equator
- Chart at high latitude (>66°N) to stress-test house calculations

### Position tolerances
- Major planets: positions must match references within ±1 arcsecond
- Asteroids/Eris (Keplerian fallback): within ±2 arcminutes
- Houses (Placidus): within ±1 arcsecond
- Vedic positions = tropical − ayanamsa (verify exactly)

### Round-trip tests
Add a person → compute chart → render → assert the person appears in DB and the chart contains expected sign placements.

### Synastry sanity tests
- Person × themselves: every aspect is conjunction at 0° orb
- Two charts 12h apart at same location: Moon should differ by ~6.5°

### CI
Provide a `Makefile` or `pytest`-runnable test suite. No CI service required for v1; run locally.

---

## 14. Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Unknown birth time | Allow chart but disable Ascendant, MC, houses, Vertex, time-sensitive Lots. Print prominent warning. |
| Approximate birth time | Compute as given; print orb-of-uncertainty for Ascendant/MC (±15°/hour of error) |
| Pre-1582 dates (Julian calendar) | Accept but warn user; Swiss Ephemeris handles correctly when given as Julian Day |
| Polar latitudes (> 66°) | Placidus/Koch fail; auto-fall-back to Whole-Sign and inform user |
| Person not found | List the available people; ask if user wants to add a new one |
| Invalid IANA tz | Reject with helpful message: "I need an IANA name like 'America/New_York', not 'EST'." |
| DST ambiguity at fall-back hour | Use IANA's first interpretation; allow user override via explicit `tz_offset_minutes` field |
| Two people with same display name | Disambiguate via tags or ID |
| Missing Swiss Eph asteroid files | Fall back to Keplerian computation silently (note in chart footer) |
| User asks for composite with someone not in group | Prompt for their birth data; do NOT auto-add — ask first |
| LibreOffice unavailable | Skip PDF; offer DOCX and explain |
| docx-js (Node) unavailable | Skip DOCX; offer Markdown and explain how to install |

---

## 15. Open Questions / Future Decisions

These are deferred until v1 is in user's hands:

1. **Group composite chart** — Is a midpoint over N>2 people meaningful? Some astrologers compute "family charts." Defer until requested.
2. **Privacy / encryption** — Should `people.json` be encrypted at rest? Birth data is sensitive (used for astrology, but also a hint at identity for fraud). v1 ships plaintext + a documented warning; revisit if users push for it.
3. **Geocoding API choice** — If the user wants automatic place lookup, do we use Nominatim (OSM, free), Google Places (paid), or just rely on Claude's web_search at runtime? v1 defers; user enters lat/lon.
4. **Interpretation depth** — How much narrative interpretation does each chart get vs. just data? v1 follows the model from this conversation: data tables + key-feature paragraphs + synthesis. Refine via evals.
5. **Symbol rendering in DOCX** — Use Unicode glyphs (☉ ☽ ♂) in tables, or text labels ("Sun"/"Moon")? Glyphs look better but font compatibility varies. v1: glyphs in headings, text labels in tables. Revisit.
6. **Caching** — Should chart computations be cached? The same person's natal chart is computed many times across calls. v1: no cache (computation is fast enough); add later if profile shows it's needed.

---

## 16. Appendix A: Algorithmic References

The implementation can lift these algorithms verbatim from the design conversation:

| Component | Source location in conversation | Notes |
|---|---|---|
| Tropical chart computation | First chart turn | Uses `swe.calc_ut` + `swe.houses` |
| Vedic computation | Multi-system turn | Uses `swe.set_sid_mode(swe.SIDM_LAHIRI)` and `FLG_SIDEREAL` |
| Nakshatra calculation | Multi-system turn | 27 mansions × 800 arcmin; pada = subdivision into 4 |
| Vimshottari Dasha | Multi-system + progression turns | Birth lord from Moon's nakshatra; balance from position within nakshatra |
| BaZi pillars | Multi-system turn | Year via Lichun cutoff; Day pillar via JD-mod-60 from anchor (J2000 = Wu Yin); month/hour from year-stem and day-stem rules |
| Hellenistic Lots | Multi-system turn | Day formulas for day chart; Spirit = ASC + Sun − Moon |
| Annual profection | Progression turn | (age mod 12) + 1; whole-sign from ASC |
| Zodiacal Releasing | Progression turn | L1 periods in years; L2 in months; transition to next sign at end |
| Solar arc | Progression turn | Entire chart + (progressed Sun − natal Sun) |
| Secondary progression | Progression turn | JD = natal JD + (years_elapsed); recompute everything |
| Davison composite | Synastry turn | Cast a real chart for midpoint date/time/place |
| Midpoint composite | Synastry turn | Per-pair midpoint, shorter-arc rule |
| Keplerian fallback for Eris/Chiron etc. | Synastry turn | Solve E − e·sin(E) = M iteratively; standard orbit-to-ecliptic transform |
| House overlay | Synastry turn | Walk partner's planets through self's cusps |
| Davison location | Synastry turn | Simple lat/lon midpoint (good enough for short distances; may want great-circle midpoint for global cases) |

---

## 17. Appendix B: SKILL.md Outline (for the implementer)

The skill's `SKILL.md` should look roughly like:

```markdown
---
name: group-synastry
description: Compute detailed astrological birth charts, synastry, and composite charts for individuals and pairs in a private group database. Use this skill whenever the user mentions synastry, composite charts, natal/birth charts, Vedic charts, BaZi, progressions, transits, Solar Returns, dashas, or asks anything about astrological compatibility between two named people. Trigger even when the user doesn't explicitly say "astrology" — phrases like "how do Alex and Jordan get along chart-wise" or "what's the chart for May 1 1966" should fire this skill. Also use when adding or managing people in the user's astrology database.
---

# group-synastry

[~50 lines explaining: detect environment → read DB → identify request type → CLARIFY → run appropriate script → render]

## Core principle: clarify before computing
Always ask the user to confirm meaningful choices (which system, output format, target date for predictive, depth) before running computations. Defaults only apply when the user explicitly says "just go" or has set persistent preferences in settings.json. See the "When to ask" subsection below for the full rule set. This is the most important behavior in this skill.

## Adding people
[brief: schema reminder, point to db.py]

## Computing charts
[brief: list of script entry points and when to use each]

## When to ask vs. when to proceed
[brief: lift the rules from spec §9.4 — always ask about system/format/date for substantial work, don't ask when user has been specific or is iterating on prior result, never more than 2 questions at once, prefer ask_user_input_v0]

## Output formats
[brief: how to choose md/docx/pdf]

## When to consult reference files
[brief: only consult vedic.md when computing Vedic charts, etc.]

## Pick-and-choose principle
[reinforce: never run "everything" by default; ask user what they want]
```

Keep it under 400 lines. Push detailed interpretation guidance into `references/` files that load only when needed.

---

## 18. Hand-off Checklist for Claude Code

When this spec is handed to Claude Code, the implementer should:

- [ ] Create the directory structure under `~/.claude/skills/group-synastry/`
- [ ] Implement Phase 1 first; produce a working MVP for Western tropical
- [ ] Run the skill end-to-end on Alex + Jordan (the canonical test case from this conversation)
- [ ] Validate computed positions against the chart in the synastry-reading.docx artifact already generated
- [ ] Build out Phases 2–5 incrementally, with tests passing at each stage
- [ ] Use the skill-creator's eval workflow to test triggering accuracy
- [ ] Document install instructions for both Claude Code and Claude.ai modes in `README.md`
- [ ] Package the final skill with `python -m skill_creator.scripts.package_skill <path>` if available

---

*End of specification.*
