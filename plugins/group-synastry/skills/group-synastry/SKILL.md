---
name: group-synastry
description: Compute detailed astrological birth charts, synastry, and composite charts for individuals and pairs in a private group database. Use this skill whenever the user mentions synastry, composite charts, natal/birth charts, Vedic charts, BaZi, progressions, transits, Solar Returns, dashas, or asks anything about astrological compatibility between two named people. Trigger even when the user doesn't explicitly say "astrology" — phrases like "how do Alex and Jordan get along chart-wise" or "what's the chart for June 15 1988" should fire this skill. Also use when adding or managing people in the user's astrology database.
---

# group-synastry

Maintain a small private database of people's birth data and produce detailed
charts, synastry, composite/Davison, and (in later phases) predictive
analyses across multiple astrological systems. **Phase 1 (current)** covers
Western tropical natal + synastry + composite + Davison + Markdown.

## Core principle: clarify before computing

This is the **single most important behavior**. Before running any
computation, ask the user to confirm meaningful choices — which system,
output format, target date for predictive work, and depth — when those
choices haven't already been specified. Defaults exist as fallbacks for
"just go," not as silent assumptions.

**Always ask about** (when not already specified):
- Which astrological system — Western tropical (default), Vedic, Hellenistic, Chinese BaZi
- Output format — inline Markdown (default), `.docx`, `.pdf`
- Target date — for any predictive request (default offer: today)
- House system — Placidus is the default; Whole-Sign / Equal / Koch on request
- **Interpretation depth** — every chart request offers `none` / `min` / `max`:
  - **none** — data tables only (current default; respects readers who just want the numbers)
  - **min** — ~500 words: Sun sign, Moon sign, Ascendant, 3 tightest aspects
  - **max** — ~2500–4000 words: each planet in sign + house, each major aspect, asteroid commentary (Chiron/Lilith/Ceres/Eris), retrograde planets, element + modality balance, chart shape

  Present as a single AskUserQuestion with three options. **Skip the question if `settings.default_interpretation_level` is set** (and use that value), or if the user already specified ("give me a max interpretation for…", "just the data"). Interpretation prose is always **appended after** the data tables — never interleaved — so a numbers-only reader can stop scrolling at the Aspects section.

  > **Tip:** users who consistently want full interpretation can set `default_interpretation_level = "max"` once via `python scripts/lib/settings.py set default_interpretation_level max`, and the question is suppressed thereafter.

**Don't ask when**:
- The user has already given specifics ("Vedic chart for Alex with Lahiri ayanamsa")
- It's a quick conversational question ("what's Alex's Sun sign?")
- The user is iterating on a recent result ("now do that as a PDF")
- A persistent preference covers it (`settings.json` overrides per-call clarification)

**Never more than 2 questions per turn.** Pick the most material decision
and default the rest with a brief inline note ("I'll use Placidus and
inline markdown unless you say otherwise").

## Dependencies (preflight)

The scripts need `pyswisseph` (required for every chart) and, for richer
output, Node + a project `npm install` (`.docx`) and LibreOffice (`.pdf`).
**Run the dependency check once at the start of a charting session** — not
every turn — and remember the result:

```bash
python scripts/check_env.py
```

It prints a per-item table, the exact install command for anything missing,
and a final `SUMMARY core_ok=true|false …` line. Act on it as follows:

- **Core missing (`pyswisseph` or Python < 3.10) — this blocks all charts.**
  - On **Claude.ai** (the check prints `Environment: Claude.ai sandbox`): the
    sandbox is ephemeral, so just install it — `python -m pip install -r
    requirements.txt` — no need to ask.
  - On **Claude Code** (local machine): tell the user it's needed, show the
    command from the check's output, **ask for confirmation, then install.**
    Installing packages changes their machine — don't do it silently.
- **Optional missing (Node / `node_modules` / LibreOffice).** Do *nothing*
  unless the user actually wants that format. When they request `.docx`/`.pdf`
  and the dep is absent, **explain and offer the choice**: install it (show the
  command; for system installs like LibreOffice via `brew`/`apt`, always ask),
  or take the fallback — Markdown if `.docx` can't render, `.docx` if `.pdf`
  can't. Never block a chart on an optional dependency.
- If a script ever fails with a `pyswisseph`-not-installed error, you skipped
  the preflight — run `check_env.py` and handle as above.

## How invocations flow

0. **Preflight** per §"Dependencies" above, once per session.

1. **Detect environment.** `scripts/lib/env.py` → `data_dir()` returns the
   right database path: `~/.config/group-synastry/people.json` in Claude
   Code, or `/mnt/user-data/uploads/people.json` (read) /
   `/mnt/user-data/outputs/people.json` (write) on Claude.ai.

2. **Read the database.** Run `python scripts/db.py list` to see who's in
   the group, or `python scripts/db.py show <id>` for a specific person.

3. **Identify the request.** Map the user's phrasing onto one of:
   - DB management (add/list/update/remove/tag) → `db.py`
   - Individual natal chart → `chart.py natal <id>`
   - Synastry between two people → `synastry.py <a> <b>`
   - Composite (midpoint or Davison) → `composite.py midpoint|davison <a> <b>`

4. **Clarify** per §"Core principle" above. Skip if the user was specific.

5. **Run the appropriate script.** Each script accepts `--json` for
   programmatic use or prints Markdown by default.

6. **Render and present.** For inline display, just print the Markdown
   that the script returns. For `.docx` / `.pdf` output, pipe the
   `--json` payload through `render_docx.py` / `render_pdf.py`:

   ```bash
   python scripts/chart.py natal alex --json | \
     python scripts/render_docx.py --output alex-natal.docx
   python scripts/synastry.py alex jordan --json | \
     python scripts/render_pdf.py --output syn-alex-jordan.pdf
   ```

## Cohorts (groups of people)

The database supports **cohorts** — named groups of people you want to collect astrological lore about. Each cohort has an id, display name, optional description, and a list of member person-ids. Cohorts are top-level in `people.json` (schema v2); a person can belong to multiple cohorts.

**When a user references "the family" / "the work group" / a cohort by name**, scope chart operations to that cohort. Common workflow:

```bash
# Create a cohort with initial members
python scripts/db.py cohort add --json '{
  "id": "lumina", "display_name": "Lumina",
  "description": "Family/inner circle",
  "members": ["alex", "jordan", "casey"]
}'

# Make it the active cohort (subsequent chart outputs route under cohorts/lumina/)
python scripts/db.py cohort set-active lumina

# Or override per call
python scripts/render_pdf.py -o foo.pdf --cohort workgroup < chart.json
```

**Cohort lore lives in `cohorts/<id>/notes.md`** — a plain markdown file alongside the chart subfolders. This is the place to accumulate observations, recurring themes, references between charts, and (future) embedded media. The notes file is *shared* with cohort members via the folder share; the DB stays private.

**Migration from a flat v1 database:** `python scripts/db.py cohort migrate --name <id> --display "Display Name"` creates a cohort and adds *all* existing people to it. One-shot upgrade.

## Adding people

Schema (spec §6.1):

```json
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
    "time_accuracy": "exact"
  },
  "tags": ["family"]
}
```

**Hard rules:**
- `tz` must be a valid IANA name (`America/New_York`, not `EDT`). The skill
  rejects abbreviations and points at the right IANA equivalent.
- `lat`/`lon` are signed decimals (North/East positive, South/West negative).
- `time_accuracy` is one of `exact`, `approximate`, `noon-default`,
  `unknown`. When `unknown`, the skill computes the chart **without**
  Ascendant, MC, IC, Descendant, Vertex, or houses, and warns the user.

To add a person:

```bash
python scripts/db.py add --json '{
  "display_name": "Alex",
  "birth": {"date": "1988-06-15", "time": "08:20",
            "tz": "America/Chicago",
            "lat": 41.8781, "lon": -87.6298,
            "place_label": "Chicago, IL",
            "time_accuracy": "exact"}
}'
```

If the user supplies a timezone abbreviation, prompt them for the IANA
zone (or look it up: EDT/EST → `America/New_York`, PDT/PST →
`America/Los_Angeles`, etc.). Don't silently substitute one — the user's
location matters (e.g. EST in Indiana is `America/Indiana/Indianapolis`).

## Computing charts

**Natal (Western tropical):**

```bash
python scripts/chart.py natal alex --house-system placidus
```

Outputs Markdown by default; pass `--json` for structured data. The natal
chart always includes (per spec D6): Sun, Moon, Mercury, Venus, Mars,
Jupiter, Saturn, Uranus, Neptune, Pluto, **Chiron**, **Lilith** (Mean
Apogee), **Ceres**, **Eris**, True Node + South Node, Ascendant,
Midheaven, Descendant, IC, Vertex.

**Synastry:**

```bash
python scripts/synastry.py alex jordan
```

Produces inter-aspects (tightest first) plus house overlays in **both**
directions — Alex's planets in Jordan's houses *and* Jordan's planets in
Alex's houses. Missing either direction is incomplete.

**Composite (midpoint + Davison):**

```bash
python scripts/composite.py midpoint alex jordan
python scripts/composite.py davison  alex jordan
```

Midpoint composite uses the shorter-arc rule per spec §16. Davison casts
a real chart for the great-circle/temporal midpoint between the two
births.

When the user asks for "the composite," default to **midpoint** and offer
to also compute Davison ("want me to also compute the Davison? It's the
chart for the literal midpoint moment and place between your births.").

## Pick-and-choose principle

Never run "everything" by default. When the user asks for "Alex's chart"
without specifying a system, ask which one. When they say "everything,"
list what would be included and confirm before running. Predictive
features are never auto-included — they require an explicit ask.

## Generating interpretation (when requested)

Interpretation prose is **LLM-authored, not skill-authored** — the Python
scripts compute the chart but cannot generate text. When the user picks
`min` or `max` interpretation:

1. Run the chart computation as usual (`chart.py natal alex --json` or
   the synastry/composite equivalent). Save the JSON output.
2. Read the chart data. Write the interpretation as a JSON file:

   ```json
   {
     "sections": [
       {"heading": "Sun in Taurus, 7th house",
        "body": "Markdown prose with **bold**, *italic*, lists, and [links](https://...) supported."},
       {"heading": "Moon in Virgo, 11th house",
        "body": "..."}
     ]
   }
   ```

   Each `body` is markdown — `marked` parses it on the Node side.
3. Render:

   ```bash
   # PDF / DOCX
   python scripts/render_pdf.py -o out.pdf --interpretation interp.json < chart.json
   # Plain markdown — chart.py / synastry.py / composite.py also take --interpretation
   python scripts/chart.py natal alex --interpretation interp.json
   ```

   The renderer appends the interpretation **after** the data tables.

### Sidecar persistence and round-tripping

When `render_docx.py` or `render_pdf.py` is given `--interpretation`, it
**also writes** `<output>.interpretation.md` next to the rendered file
(e.g., `alex.pdf` + `alex.interpretation.md`). The sidecar is plain
markdown — human-editable and re-loadable:

```bash
# First render: produces alex.pdf AND alex.interpretation.md
python scripts/render_pdf.py -o alex.pdf --interpretation interp.json < chart.json

# Edit alex.interpretation.md in your editor of choice…

# Re-render with the edited prose; same flag accepts .md or .json
python scripts/render_pdf.py -o alex-v2.pdf --interpretation alex.interpretation.md < chart.json
```

Pass `--no-sidecar` to skip emission. `--interpretation` on the chart
scripts (`chart.py natal alex --interpretation foo.md`) also accepts
either format, so the round-trip workflow extends to markdown output.

**`min` (~500 words)** — three to five sections:
- Sun in sign + house (1 paragraph)
- Moon in sign + house (1 paragraph)
- Ascendant in sign + ruler placement (1 paragraph)
- Three tightest aspects (combined, 1–2 paragraphs)

**`max` (~2500–4000 words)** — one section per planet (each in sign +
house, headlined "Sun in Taurus, 7th house" etc.), one section per major
aspect (conjunction/opposition/square/trine/sextile, tightest first),
short sections for retrograde planets / nodes / Chiron / asteroids, and
a closing "synthesis" section covering element + modality balance,
hemisphere emphasis, and dominant chart shape.

For synastry interpretations, structure sections around the tightest
cross-aspects and the most charged house overlays. For composite charts,
treat the composite as a chart in its own right (composite Sun in X
means "this relationship's core identity is…").

When writing interpretation, draw on the canonical references when they
exist (`references/synastry-aspects.md`, `references/asteroids-and-points.md`
— not yet built but planned per spec). Until those land, lean on
training knowledge and keep the tone observational rather than
predictive.

## When to consult reference files

`references/*.md` files load only when relevant to the current request:
- `vedic.md` — only for Vedic computations (Phase 3)
- `chinese.md` — only for BaZi (Phase 3)
- `hellenistic.md` — only for Lots / profections / ZR (Phase 3 / 4)
- `synastry-aspects.md` — for synastry interpretation depth
- `asteroids-and-points.md` — for Chiron/Eris/Lilith/Ceres interpretation

Don't read every reference file on every invocation. Open only what the
current request needs.

## Output formats

- **Markdown (default):** the script's stdout is ready to paste inline.
- **`.docx`:** `render_docx.py` shells out to `lib/render_docx.js` (Node + docx-js).
  Auto-detects natal vs. synastry vs. composite from the payload shape. Style
  tokens live in `lib/style.json` per spec §10.4.
- **`.pdf`:** `render_pdf.py` produces a `.docx` first then converts it via
  `soffice --headless --convert-to pdf`. Looks for `soffice` on PATH, then
  falls back to the macOS LibreOffice app bundle and common Linux paths.

When producing a substantial deliverable (synastry report, full natal),
ask the user about format up front unless they specified one or
`settings.json` has a default.

## Output file location

- **Claude Code:** current working directory unless the user specifies
  otherwise, OR `settings.default_output_dir` (e.g., a Proton Drive
  synced folder) if set.
- **Claude.ai:** `/mnt/user-data/outputs/`.

Filenames follow `<kind-prefix>-<names>-<YYYYMMDD>.{md,docx,pdf}`, with
short kind prefixes to keep filenames scannable:

- `natal` → no prefix; just `<name>.{ext}` (e.g. `alex.pdf`)
- `synastry` → `syn-` (e.g. `syn-alex-jordan-20260504.docx`)
- `composite` (midpoint) → `cmp-` (e.g. `cmp-alex-jordan-20260504.pdf`)
- `davison` → `dav-` (e.g. `dav-alex-jordan-20260504.pdf`)

Date suffix is optional but recommended when rendering pair charts that
may be re-cast later for different transit moments or with updated
interpretations.

### Kind-based subfolders

If `settings.default_output_subfolders` is set (a dict mapping chart kind
→ subfolder name), bare-filename `--output` arguments are routed into the
kind's subfolder automatically. Example setting::

    "default_output_subfolders": {
      "natal":     "birth-charts",
      "synastry":  "synastry",
      "composite": "synastry",
      "davison":   "synastry"
    }

With the above, `render_pdf.py -o alex.pdf` (on a natal payload) lands at
`<output-dir>/birth-charts/alex.pdf`, and `-o alex-jordan.pdf` (on a
synastry payload) lands at `<output-dir>/synastry/alex-jordan.pdf`. An
explicit subdir in `--output` (e.g. `-o custom/alex.pdf`) or an absolute
path bypasses the routing.

### Cohort-based subfolders

If `settings.active_cohort` is set (or `--cohort <id>` is passed to the
render command), a `cohorts/<id>/` prefix is added **before** the kind
subfolder. So with both `active_cohort = lumina` AND the kind mapping
above::

    render_pdf.py -o alex.pdf < natal.json
    # → <output-dir>/cohorts/lumina/birth-charts/alex.pdf

    render_pdf.py -o syn-alex-jordan.pdf < synastry.json
    # → <output-dir>/cohorts/lumina/synastry/syn-alex-jordan.pdf

`--cohort` on the command line overrides `active_cohort` for that invocation.
Explicit subdirs and absolute paths bypass *both* routing layers.

### Time-range subfolders (uncertain birth times)

When a person has `birth.time_hysteresis_minutes > 0`, the same recorded
time can yield very different houses/angles across the uncertainty window.
The skill supports rendering chart *variants* at multiple candidate times,
each landing in its own folder under
`cohorts/<id>/time-range/<pair>/<variant-label>/`.

Routing layers stack:

    render_pdf.py -o syn-alex-casey.pdf \
        --time-range-pair alex+casey \
        --time-range-label casey-1700 \
        < synastry.json
    # → <output-dir>/cohorts/<active>/time-range/alex+casey/casey-1700/syn-alex-casey.pdf

When time-range routing is active, the **kind subfolder is skipped** —
all three chart kinds (cmp/syn/dav) for a given variant land in the same
folder so the variant's chart-set lives together.

## Working with birth-time hysteresis

If the user requests a chart involving someone whose
`birth.time_hysteresis_minutes` is greater than 0:

1. **Briefly mention the uncertainty.** E.g. *"Casey's recorded time has
   ±1hr uncertainty — want time-range variants?"* This is a one-line nudge,
   not a blocker; render the recorded-time chart as requested.
2. **If the user accepts time-range generation**, run a window scan first
   to give a meaningful recommendation:

       python scripts/time_range.py scan <person>

   The scan reports the Ascendant at min/recorded/max times and counts
   sign-boundary crossings inside the window. Recommend a strategy based
   on what it found:
   - **0 boundaries** → one chart at the recorded time is enough.
   - **1 boundary** → use `asc-boundaries` (typically 2 variants).
   - **2+ boundaries** → use `asc-boundaries` (N+1 variants).
3. **Always show the full menu** as alternatives — the user may want
   `min-max` for a quick check or `every-n-minutes` for smooth coverage:

   | Strategy | What it produces |
   |---|---|
   | `min-max` | 2 charts at the window edges |
   | `every-n-minutes` | fixed step (user picks `--step`) |
   | `asc-boundaries` | adaptive: 1 chart per Asc-sign interval |

4. **Generate the variants and render** with `scripts/time_range.py render`:

       python scripts/time_range.py render <a> <b> --strategy <name> [--step MIN] [--cohort <id>]

   This computes cmp/syn/dav for each variant and lands them under the
   time-range subfolder. Defaults: all three kinds; varied person is
   auto-detected (whichever has non-zero hysteresis).

## Edge cases & error handling

| Case | Behavior |
|---|---|
| Unknown birth time | Compute chart but disable angles/houses/Vertex; warn prominently. |
| Invalid IANA tz (`"EDT"`, `"PST"`) | Reject with the IANA equivalent suggested. |
| Person not found | List who's in the group; offer to add the missing one — don't auto-add. |
| Two people with same display name | Ask which one (use IDs, tags, or birth year to disambiguate). |
| Missing Swiss Eph asteroid files | Fall back to bundled Keplerian elements (Chiron/Ceres/Eris). The chart footer notes the fallback. **Chiron precision is ±1–2° in this mode** — for arcminute Chiron, the user can install `seas_18.se1`; see the sibling README.md. Ceres and Eris remain accurate to arcminutes via the fallback. |
| Polar latitudes (>66°) where Placidus fails | Auto-fall-back to Whole-Sign and inform the user. |

## What's NOT implemented yet (later phases)

- Phase 3: Vedic, Hellenistic, Chinese BaZi
- Phase 4: progressions, transits, returns, dashas, profections, ZR
- Phase 5: group ops (compatibility matrix, batch synastry)
- Phase 6: fixed stars, locational, harmonics

If the user asks for any of these, say what's available now (Phase 1
+ 2 features) and offer to do an inline approximation if appropriate.

## Quick reference — script entry points

| Goal | Command |
|---|---|
| Check dependencies (preflight) | `python scripts/check_env.py` (add `--json` for machine output) |
| Install the core Python dep | `python -m pip install -r requirements.txt` |
| Show DB path | `python scripts/db.py path` |
| List people | `python scripts/db.py list` |
| Show one person | `python scripts/db.py show <id>` |
| Add person | `python scripts/db.py add --json '{...}'` |
| Update person | `python scripts/db.py update <id> --json '{...}'` |
| Remove person | `python scripts/db.py remove <id>` |
| Natal chart | `python scripts/chart.py natal <id>` |
| Synastry | `python scripts/synastry.py <a> <b>` |
| Midpoint composite | `python scripts/composite.py midpoint <a> <b>` |
| Davison | `python scripts/composite.py davison <a> <b>` |
| Render to .docx | `<chart-cmd> --json \| python scripts/render_docx.py -o out.docx` |
| Render to .pdf  | `<chart-cmd> --json \| python scripts/render_pdf.py -o out.pdf` |
| Markdown chart + interpretation | `python scripts/chart.py natal <id> --interpretation interp.{json,md}` |
| Render with interpretation + sidecar | add `--interpretation interp.{json,md}` to the render command; sidecar is auto-written next to the output |
| Suppress the sidecar | add `--no-sidecar` to the render command |
| List cohorts | `python scripts/db.py cohort list` |
| Show a cohort | `python scripts/db.py cohort show <id>` |
| Create a cohort | `python scripts/db.py cohort add --json '{"id":"…","display_name":"…","members":["…"]}'` |
| Add/remove cohort member | `python scripts/db.py cohort add-member <cohort> <person>` (or `remove-member`) |
| Set active cohort | `python scripts/db.py cohort set-active <id>` |
| Override cohort for one render | add `--cohort <id>` to the render command |
| Migrate v1 → v2 (single cohort) | `python scripts/db.py cohort migrate --name <id> --display "…"` |
| Set birth-time hysteresis | `python scripts/db.py update <id> --json '{"birth":{"time_hysteresis_minutes":60}}'` |
| Scan a hysteresis window | `python scripts/time_range.py scan <id>` |
| List time-range variants | `python scripts/time_range.py list <id> --strategy <min-max\|every-n-minutes\|asc-boundaries> [--step MIN]` |
| Render full time-range set | `python scripts/time_range.py render <a> <b> --strategy <name> [--step MIN] [--cohort <id>]` |

All chart commands accept `--house-system {placidus,koch,whole-sign,equal,porphyry,regiomontanus,campanus}` and `--json`.
