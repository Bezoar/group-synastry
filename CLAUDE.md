# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin marketplace** containing the `group-synastry` skill, plus its spec (`docs/specs/primary.md`) and eval suite (`evals/`). The skill computes astrological birth charts, synastry, and composite/Davison charts for a small private group. The same skill bundle runs in Claude Code (via plugin install) and on Claude.ai (uploaded as a skill).

The plugin layout — `plugins/group-synastry/skills/group-synastry/` — is referred to as **`<skill>/`** throughout this doc to keep paths readable.

**Status:** Phases 1 and 2 of 6 are built. Phase 1 = Western tropical natal + synastry + composite + Davison + Markdown. Phase 2 = `.docx` (via Node + docx-js) and `.pdf` (via LibreOffice headless) rendering with shared style tokens. Phases 3–6 (Vedic, Hellenistic, BaZi, predictive, group ops, polish) are deferred per `docs/specs/primary.md` §10. If a user asks for a deferred feature, say what's available now and offer an inline approximation if appropriate — don't pretend it works.

## Canonical documents — read these before changing behavior

**CRITICAL: when editing any file in docs/specs, if there is a file in this repo called docs/instructions/editing-specs.md, ALWAYS read and follow the instructions there.**

**When pushing an upstream sync PR to the public mirror, if `docs/instructions/upstream.md` is present, read and follow it** — it covers composing the scrubbed public PR description from the constituent private PRs.

- **`docs/specs/primary.md` — the authoritative current-state spec.** Read this first; it covers what the repo does, how the code is organized, and the load-bearing design decisions with rationale. Update it when behavior changes.
- `docs/archive/original-spec/spec.md` — the **original** Phase 1 design spec. Frozen, historical, and now **fully superseded** by `docs/specs/primary.md` (its decision log D1–D9, user stories, edge cases, and algorithmic references have all been folded into the primary spec). You shouldn't need to open it; treat `docs/specs/primary.md` as the single source of truth.
- `<skill>/SKILL.md` — the behavior contract the skill follows at runtime (clarify-first, pick-and-choose, edge-case table, interpretation workflow). Changes here change skill behavior.
- `evals/README.md` — eval design philosophy and run instructions; the coverage matrix tells you which behavior each eval pins.
- `evals/reference-charts.json` — ground-truth planetary positions for the canonical test subjects (Alex, Jordan). Treat as versioned facts; only change when the underlying ephemeris improves.
- `.claude-plugin/marketplace.json` and `plugins/group-synastry/.claude-plugin/plugin.json` — marketplace and plugin manifests; update version in `plugin.json` when shipping a phase.

## Common commands

```bash
# Run the test suite (all tests should pass; Node tests skip if Node missing)
cd plugins/group-synastry/skills/group-synastry && python -m pytest tests/ -q

# Run a single test
cd plugins/group-synastry/skills/group-synastry && python -m pytest tests/test_chart.py::test_mark_tropical_natal -v

# Install the skill into Claude Code (from inside Claude Code)
/plugin marketplace add /path/to/group-synastry-private
/plugin install group-synastry

# Install Node-side dependencies for .docx rendering (one-time)
cd plugins/group-synastry/skills/group-synastry && npm install

# Hit the CLI directly during development (from repo root)
python plugins/group-synastry/skills/group-synastry/scripts/db.py list
python plugins/group-synastry/skills/group-synastry/scripts/chart.py natal alex
python plugins/group-synastry/skills/group-synastry/scripts/synastry.py alex jordan
python plugins/group-synastry/skills/group-synastry/scripts/composite.py midpoint alex jordan
python plugins/group-synastry/skills/group-synastry/scripts/composite.py davison alex jordan

# Phase 3 (medieval/traditional): sect, dignities, 7 Hermetic lots, almuten; annual profections
python plugins/group-synastry/skills/group-synastry/scripts/medieval.py natal alex
python plugins/group-synastry/skills/group-synastry/scripts/medieval.py natal alex --json
python plugins/group-synastry/skills/group-synastry/scripts/medieval.py profection alex --age 37
python plugins/group-synastry/skills/group-synastry/scripts/medieval.py profection alex --on 2026-05-25

# Phase 2: produce .docx / .pdf (pipe --json through the renderer)
python plugins/group-synastry/skills/group-synastry/scripts/chart.py natal alex --json | \
  python plugins/group-synastry/skills/group-synastry/scripts/render_docx.py -o alex.docx
python plugins/group-synastry/skills/group-synastry/scripts/synastry.py alex jordan --json | \
  python plugins/group-synastry/skills/group-synastry/scripts/render_pdf.py -o synastry.pdf

# Graphical natal chart wheel (issue #39): .svg / .png / .pdf by output extension
python plugins/group-synastry/skills/group-synastry/scripts/chart.py natal alex --json | \
  python plugins/group-synastry/skills/group-synastry/scripts/render_svg.py -o alex-wheel.svg
python plugins/group-synastry/skills/group-synastry/scripts/render_svg.py -i alex.json -o alex-wheel.png --theme dark --aspects all
# The .docx/.pdf renderers embed the wheel at the top of natal reports by default; --no-wheel for tables-only.
# Regenerate the glyph-path data after a font change:
python plugins/group-synastry/skills/group-synastry/scripts/lib/_gen_astro_glyphs.py
```

All chart/synastry/composite/medieval scripts accept `--json` (structured output for programmatic use) and `--house-system {placidus,koch,whole-sign,equal,porphyry,regiomontanus,campanus,alcabitius}`. (`medieval.py` defaults to `alcabitius`; the others default to Placidus / `settings.default_house_system`.)

**To render unattended (no permission prompt):** invoke a script as a plain literal command — `.venv/bin/python plugins/group-synastry/skills/group-synastry/scripts/render_pdf.py -i chart.json -o out.pdf` — *not* wrapped in a shell variable (`PY=…; $PY …`), `&&` chain, or pipe. The `Bash(.venv/bin/python *)` allow rule is a **prefix match on the literal command**, so variable indirection defeats it and forces a prompt. Read chart JSON from a file with `-i FILE` rather than piping `chart.py --json | render_*.py`.

Tests bring their own fixture (`<skill>/tests/fixtures/people_test.json`, gitignored) — they do not touch the user's real `people.json`.

## Architecture

### Two-environment design (one skill bundle)

`<skill>/scripts/lib/env.py` is the dispatcher. It detects whether `/mnt/user-data/{uploads,outputs}` exists (→ Claude.ai sandbox) or not (→ Claude Code) and returns the right paths for `people.json`, `settings.json`, output files, and the Swiss Ephemeris data search path. **Never hard-code a path** in any other script — call into `env.py`. Adding a new file type (e.g., a cache) means extending `env.py`, not branching in callers.

`env.py`'s `BUNDLED_EPHE_DIR = Path(__file__).resolve().parents[2] / "ephe"` resolves to `<skill>/ephe/` and depends on the skill keeping its current internal structure (`scripts/lib/env.py` → two levels up is the skill root). If you nest things differently, this needs to change.

### Strict per-body ephemeris source (no silent fallback)

`<skill>/scripts/lib/ephem.py` enforces a *best source* per body and **raises `EphemerisFileMissing`** instead of silently degrading to the Keplerian path. This was deliberate: silent fallback produced different positions on different machines depending on which `.se1` files happened to be installed, breaking eval reproducibility. If a caller wants the Keplerian fallback, it must pass `force_source="keplerian_jpl_j2000"` explicitly.

- Sun/Moon/planets/True Node/Lilith → `swisseph_builtin` (no file needed, arcsecond accuracy via Moshier).
- Chiron / Ceres / Pallas / Juno / Vesta → `swisseph_with_seas18` (the bundled `<skill>/ephe/seas_18.se1`).
- Eris → `keplerian_jpl_j2000` (no bundled Swiss Eph file for asteroid 136199; Keplerian is arcminute-accurate for TNOs).

When editing this file: don't add a body without also picking its best source and listing it in `_BODY_SOURCES`. The `KEPLERIAN_NAMES` set and `_SOURCE_REQUIRES_FILE` map must stay consistent.

### Clarify-first / pick-and-choose / D6 always-included bodies

These three principles in `SKILL.md` are load-bearing:

1. **Clarify before computing** when the user hasn't specified system / format / target date / depth. Max 2 questions per turn; default the rest with a brief inline note. Skip clarification if the user was already specific, is iterating on a previous result, or has a matching preference in `settings.json`.
2. **Never run "everything" by default.** If asked for "Alex's chart" with no system, ask which one. Predictive features always require an explicit ask.
3. **D6 always-included bodies** in any natal or synastry: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, **Chiron, Lilith (Mean Apogee), Ceres, Eris**, True Node, ASC, MC. Missing any of these is a spec failure (the behavioral evals check this explicitly).

### Timezones are IANA-only

`<skill>/scripts/lib/tz.py` rejects abbreviations like `EDT`/`PST` and points at the IANA equivalent (the abbreviation table is curated, not auto-substituted, because the same abbreviation maps to different IANA zones depending on the location — e.g., EST in Indiana is `America/Indiana/Indianapolis`). All datetime → JD conversion goes through `to_julian_day_ut`, which uses `zoneinfo` for historically correct DST.

### Synastry overlays must be bidirectional

`synastry.py` returns `overlays_a_in_b` **and** `overlays_b_in_a`. Missing either direction is incomplete per spec §16 and is tested by the behavioral evals. Same applies if you add new pairwise computations.

### Phase 2 rendering: Python ↔ Node bridge for `.docx`, LibreOffice for `.pdf`

`<skill>/scripts/render_docx.py` is a thin Python wrapper that spawns `node <skill>/scripts/lib/render_docx.js`, piping the chart payload (`{kind, chart, style, interpretation?, wheel_png?}`) on stdin. The Node side uses `docx@9.x` and `marked@18.x` (project-local via `<skill>/package.json` — not global) because docx-js has no maintained Python port and the spec's validation path lives in the JS ecosystem (§10.2). Style tokens live in `<skill>/scripts/lib/style.json` and match spec §10.4 (fonts, hex colors without `#`, point sizes that the Node side doubles to half-points for docx-js).

### Graphical chart wheel: pure-Python SVG, glyphs-as-paths (issue #39, spec §6.5)

`<skill>/scripts/lib/wheel.py` builds a natal chart wheel as **SVG** in pure Python (no Node). `render_wheel(chart, *, theme, aspects, show_tints)` maps ecliptic longitude to `φ = 180 − (λ − asc_lon)` so the Ascendant sits at the left and longitude runs counter-clockwise. **All geometry is in the `WheelGeometry` dataclass and all colours in `WheelColors`** — pixel-push there, not in the drawing code. Time-unknown charts render a partial wheel (ring + planets, no houses/angles).

Astrological symbols are drawn as SVG `<path>` outlines, **not** as font text: `lib/astro_glyphs.json` (generated by `lib/_gen_astro_glyphs.py` from the bundled **Astronomicon** font) holds each glyph's path/advance/bbox. This is deliberate — it makes the wheel render identically across Chrome, LibreOffice, and browsers with **zero runtime font dependency**, which is what lets the embedded PNG look the same in the Claude.ai sandbox as locally. The font ships verbatim under `<skill>/assets/fonts/astronomicon/` with its OFL licence (unmodified → no Reserved-Font-Name rename needed). **`_gen_astro_glyphs.py` carries the verified ASCII→symbol map** (vendor doc + visual specimen, per the "verify, never recall" rule); rerun it only when the font changes. `fonttools` is a dev/build dependency for that generator, not a runtime one.

`<skill>/scripts/lib/rasterize.py` turns SVG into PNG/PDF: headless **Chrome** first (it polls for the output file then terminates the process, because modern `--headless=new` writes the file without exiting), then **LibreOffice** as fallback. `<skill>/scripts/render_svg.py` is the CLI (output format follows the `.svg`/`.png`/`.pdf` extension; `--aspects major|all`, `--theme`, `--scale`, `--no-tints`). Natal-only; synastry/composite wheels are a follow-up.

**Themes:** `--theme light|dark`. Wheel palettes are `WheelColors` instances selected by `lib/wheel.py::colors_for(theme)`. `dark` is wheel-forward: dark field, light opaque pastel ring, black sign glyphs, bright cusps/angles/indicator lines, hard-aspect red brightened to match soft-aspect blue. `WheelColors` carries `sign_ink` (sign-glyph colour, falls back to `ink`) and `tint_opacity` (zodiac-band fill) so a theme can vary the ring independently of the field. Document page/table colours come from `style.json` themes. Adding a wheel theme = a `WheelColors` in `colors_for` + (if used in reports) a matching `style.json` theme + the name in the three `--theme` `choices` lists.

**Embedding:** `render_docx.py::build_wheel_png_b64` renders the wheel PNG and the renderer passes it in the payload; `lib/render_docx.js::renderNatal` inserts an `ImageRun` **below the heading/birth-info block and above the data tables** of natal reports. Natal-only, and it **degrades safely** — a missing rasterizer logs a warning and produces a text-only report rather than failing. `--no-wheel` opts out. `test_natal_docx_embeds_wheel_below_heading_above_tables` pins the heading→wheel→positions ordering; `test_wheel.py` covers the geometry/glyph/collision/partial-wheel behavior.

### Interpretation prose is LLM-authored, not skill-authored

The chart scripts are deterministic computation (positions, aspects, houses) and emit no prose. When the user asks for `min` or `max` interpretation, **Claude writes the prose** in this conversation, saves it as a JSON file `{sections: [{heading, body}]}` where `body` is markdown, and passes that via `--interpretation FILE` to one of:

- `render_docx.py` / `render_pdf.py` (for `.docx` / `.pdf` output)
- `chart.py natal <id>` / `synastry.py <a> <b>` / `composite.py midpoint|davison <a> <b>` (for markdown output)

The renderer appends an "Interpretation" section after all chart data so number-only readers can stop scrolling at the Aspects table — `test_interpretation_renders_after_data_with_markdown_formatting` pins this ordering. `lib/render_docx.js` uses `marked.Lexer` to walk the markdown AST and emit docx-js paragraphs, lists, and `ExternalHyperlink`s; in-body headings are forced to h3 so the section's h2 stays dominant. Image tokens currently render as `[image: alt]` placeholders — future media-link work just needs to handle the `image` token case in `inlineRuns()`.

### Output is routed by chart kind via `default_output_subfolders`

`lib/settings.py` exposes `subfolder_for_kind(kind)`, consulted by `render_docx.py::resolve_output_path()`. When `--output` is a *bare filename* (no path separator) AND the setting has a mapping for the detected/passed kind, the path is rewritten to `<output-dir>/<subfolder>/<filename>`. Explicit subdir prefixes in `--output` and absolute paths both bypass the routing — escape hatches preserved. Detection is done up front in `_main()` (before `resolve_output_path` is called) so the kind threads through both routing and rendering consistently. See `test_settings.py::test_resolve_output_path_routes_bare_filename_to_kind_subfolder` for the pinned behavior.

### Cohorts and routing layers

Phase 3 (issue #9): `people.json` schema v2 adds top-level `cohorts: [{id, display_name, description, created_at, members: [...]}]`. Cohort prose notes live OUTSIDE the DB at `cohorts/<id>/notes.md` (a folder artifact, not a JSON field) so cohort members with access to the synced folder can read and edit them while the DB stays private.

`resolve_output_path(path_arg, kind, cohort, time_range_pair, time_range_label)` applies **up to three layers** of routing for bare-filename outputs: cohort prefix first, then EITHER time-range prefix (`time-range/<pair>/<label>/`) OR kind subfolder. Time-range and kind layers are mutually exclusive — when time-range is active, the kind subfolder is skipped so all chart kinds for a variant share one folder. All layers are optional. Ordering pinned by `test_cohorts.py::test_resolve_output_path_with_active_cohort_routes_under_cohorts` and `test_time_range.py::test_time_range_routing_skips_kind_subfolder`.

`env.people_json_path()` now consults `settings.people_db_dir` for the DB location (falls back to `data_dir()` for backward compat). This lets users move `people.json` into a synced folder while keeping `settings.json` local — sharing happens at the cohort folder level, never at the DB level.

`db.py` gains a `cohort` subcommand group with the obvious CRUD verbs plus `set-active <id>` (writes to settings) and `migrate --name <id>` (one-shot v1→v2: creates a cohort and adds all existing people).

### Birth-time hysteresis and time-range variants

Phase 3.5 (issue #12): person records gain optional `birth.time_hysteresis_minutes` (non-negative integer half-width of the uncertainty window; default 0). Read via `db.get_hysteresis_minutes(person)`. Explicit-0 writes are not persisted — keeps the on-disk records clean for the common case.

`scripts/time_range.py` implements three sampling strategies (`min-max`, `every-n-minutes`, `asc-boundaries`) plus a `scan` subcommand that returns the Ascendant at min/recorded/max times and counts sign-boundary crossings inside the window. The `asc-boundaries` strategy bisects the window to find each Asc sign crossing and emits one variant per resulting sign interval — this is the astrologically informed default.

The `render` subcommand drives the whole pipeline in-process (no subprocess per chart kind) and routes through the new `--time-range-pair` / `--time-range-label` flags on `render_pdf.py` / `render_docx.py`. Variants land at `cohorts/<id>/time-range/<pair>/<varied-id>-HHMM/` — note the pair-id uses `+` (`alex+casey`) to distinguish from filename-level `-` separators.

### Interpretation source is persisted via a sidecar

When `render_docx.py` / `render_pdf.py` receive `--interpretation`, they write `<output_stem>.interpretation.md` alongside the rendered file. The sidecar is plain markdown (human-editable), and `parse_interpretation_file()` in `render_docx.py` accepts either `.json` or `.md`, so the workflow round-trips: render → edit sidecar → re-render with `--interpretation sidecar.md`. `--no-sidecar` opts out of sidecar emission. This means the prose Claude writes is not lost when the chat is cleared and not stuck inside the binary PDF — it lives as an editable text file in the same folder as the rendered document.

`<skill>/scripts/render_pdf.py` produces the `.docx` first and then converts it via `soffice --headless --convert-to pdf`. `locate_soffice()` checks PATH first, then falls back to `/Applications/LibreOffice.app/Contents/MacOS/soffice` (macOS), `/usr/bin/libreoffice` (Linux), and a few other common paths. The Claude.ai sandbox has `soffice` on PATH; macOS dev machines typically don't, hence the fallback list.

`detect_kind()` on either side discriminates payloads by shape: `overlays_a_in_b` → synastry, `method` + `points` → composite, `planets` + `display_name` → natal. Tests assert all three render to a valid zip-with-`word/document.xml`. If a fourth chart kind is ever added, both `detect_kind`s and the per-kind renderers on the JS side need a matching branch.

### Composite charts: midpoint vs. Davison

Different algorithms, both shipped:

- **Midpoint** (`midpoint_composite` in `composite.py`) — per-body shorter-arc midpoint of the two natal longitudes. Houses are equal-house from the midpoint Ascendant; we don't try to recompute Placidus on a derived chart.
- **Davison** — casts a real natal chart at the temporal midpoint (UT) and great-circle spatial midpoint of the two birth events; reuses `compute_natal` on a synthetic person.

When the user asks for "the composite" without qualifying, default to **midpoint** and offer Davison.

### Medieval / traditional layer (Phase 3, increment 1)

`<skill>/scripts/lib/medieval.py` layers the deterministic traditional-astrology substrate on top of `compute_natal`: **sect** (diurnal/nocturnal, sect light, benefic/malefic of the sect, orientality), **essential dignities** (domicile, exaltation, triplicity-by-sect, Egyptian term, Chaldean face; detriment/fall; peregrine; the +5/+4/+3/+2/+1 score; and the **almuten** of a degree — the almuten of the Ascendant is surfaced), the seven **Hermetic Lots** (Fortune, Spirit, Eros, Necessity, Courage, Victory, Nemesis — all via one uniform day/night-reversing rule, `lot_value`), and **annual profections** (profected sign/house, lord of the year, monthly sign, and the lord of the year's natal condition), plus **antiscia / contra-antiscia** (with within-orb contacts), and **mutual reception** (by domicile/exaltation). `compute_medieval(person, house_system="alcabitius")` assembles a `MedievalChart`; the CLI is `medieval.py natal|profection <id>` (profection is predictive → a separate explicit subcommand, never part of natal output); `render_md.render_medieval()` / `render_profection()` render Markdown. Alcabitius (Swiss Eph `B`) was added to `ephem.HOUSE_SYSTEM_CODES` and is the medieval default.

Two load-bearing constraints from `docs/specs/medieval.md`:
- **Reference tables are verified, never recalled** (spec §4). The dignity tables carry source citations in comments, were cross-checked across ≥2 authoritative sources, and use the **Egyptian** terms (the medieval default — *not* the Ptolemaic set). `test_medieval.py` has integrity guards (every Egyptian-term row sums to 30°; each planet rules the right count of domiciles) so a future transcription error fails loudly.
- **Computation only — no prose, no citations yet.** The medieval CLI emits numbers and dignity states, like the other chart scripts. The citation-bearing interpretation layer (spec §5) depends on a verified corpus built as a separate sub-project (`docs/research/biblio.md`, issue #34) and is deliberately **not** wired here — so there is no code path that could emit an un-grounded citation. Also deferred: the medieval `.docx`/`.pdf` branch (a new case in both `detect_kind`s), the rest of the §3 techniques (firdaria, returns, lunar mansions, planetary hours, fixed stars, temperament, …), primary directions (#33), and the `SKILL.md` "which system?" clarify-step (so the layer is direct-invocation only, not yet surfaced through natural language).

## When changing the skill

- If you change `SKILL.md`'s frontmatter description: re-run the trigger evals (`evals/trigger-evals.json`) — see `evals/README.md` for the loop. The description is optimized against those 52 queries.
- If you change a computation: re-run `pytest tests/ -q` and re-grade the behavioral evals against `evals/reference-charts.json`. Tolerances are documented in `evals/README.md` (±1 arcmin for major planets, ±2 for asteroid Keplerian fallback, ±5 for angles).
- If you change `docs/specs/primary.md`: update the affected behavioral evals to match (the README §"Updating the Eval Suite" lists the typical mappings).
- Phase ordering matters: don't start Phase 3 (Vedic/Hellenistic/BaZi) before Phase 2 (`.docx`/`.pdf`) is wired up, because Phase 3's output volume needs polished formats to be useful.

## Things that look wrong but aren't

- `<skill>/ephe/seas_18.se1` is committed despite `.gitignore` having `ephe/*.se1` — it was force-added (commit `8d9bdab`) because the skill needs to ship with arcminute Chiron accuracy out of the box. Don't "fix" this by removing the file. This file is also the reason the whole repo is AGPL-3.0 (it's distributed under AGPL by upstream Swiss Ephemeris).
- `people.json` and `settings.json` are gitignored globally. The tests use a separate fixture; don't add the user's real DB to the repo.
- `chart.py`'s `PlanetEntry.source` field reports `"swisseph"` / `"keplerian"` / `"composite"`. The `lib/ephem.py` `BodyPosition.source` reports the more specific code (`swisseph_builtin` / `swisseph_with_seas18` / `keplerian_jpl_j2000`). The renderer flattens these — don't unify them without checking the eval grader.
- `docs/archive/original-spec/spec.md` still references the old `skill/` and `~/.claude/skills/group-synastry` paths internally. It's a historical/frozen document — don't update it; the marketplace layout is documented here and in the live READMEs.
