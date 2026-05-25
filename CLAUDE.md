# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin marketplace** containing the `group-synastry` skill, plus its spec (`docs/specs/primary.md`) and eval suite (`evals/`). The skill computes astrological birth charts, synastry, and composite/Davison charts for a small private group. The same skill bundle runs in Claude Code (via plugin install) and on Claude.ai (uploaded as a skill).

The plugin layout — `plugins/group-synastry/skills/group-synastry/` — is referred to as **`<skill>/`** throughout this doc to keep paths readable.

**Status:** Phases 1 and 2 of 6 are built. Phase 1 = Western tropical natal + synastry + composite + Davison + Markdown. Phase 2 = `.docx` (via Node + docx-js) and `.pdf` (via LibreOffice headless) rendering with shared style tokens. Phases 3–6 (Vedic, Hellenistic, BaZi, predictive, group ops, polish) are deferred per `docs/specs/primary.md` §10. If a user asks for a deferred feature, say what's available now and offer an inline approximation if appropriate — don't pretend it works.

## Canonical documents — read these before changing behavior

**CRITICAL: when editing any file in docs/specs, if there is a file in this repo called docs/instructions/editing-specs.md, ALWAYS read and follow the instructions there.**

- **`docs/specs/primary.md` — the authoritative current-state spec.** Read this first; it covers what the repo does, how the code is organized, and the load-bearing design decisions with rationale. Update it when behavior changes.
- `docs/archive/original-spec/spec.md` — the **original** Phase 1 design spec. Frozen, historical, and now **fully superseded** by `docs/specs/primary.md` (its decision log D1–D9, user stories, edge cases, and algorithmic references have all been folded into the primary spec). You shouldn't need to open it; treat `docs/specs/primary.md` as the single source of truth.
- `<skill>/SKILL.md` — the behavior contract the skill follows at runtime (clarify-first, pick-and-choose, edge-case table, interpretation workflow). Changes here change skill behavior.
- `evals/README.md` — eval design philosophy and run instructions; the coverage matrix tells you which behavior each eval pins.
- `evals/reference-charts.json` — ground-truth planetary positions for the canonical test subjects (Alex, Jordan). Treat as versioned facts; only change when the underlying ephemeris improves.
- `.claude-plugin/marketplace.json` and `plugins/group-synastry/.claude-plugin/plugin.json` — marketplace and plugin manifests; update version in `plugin.json` when shipping a phase.

## Common commands

```bash
# Run the test suite (37 tests should pass; Node tests skip if Node missing)
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

# Phase 2: produce .docx / .pdf (pipe --json through the renderer)
python plugins/group-synastry/skills/group-synastry/scripts/chart.py natal alex --json | \
  python plugins/group-synastry/skills/group-synastry/scripts/render_docx.py -o alex.docx
python plugins/group-synastry/skills/group-synastry/scripts/synastry.py alex jordan --json | \
  python plugins/group-synastry/skills/group-synastry/scripts/render_pdf.py -o synastry.pdf
```

All chart/synastry/composite scripts accept `--json` (structured output for programmatic use) and `--house-system {placidus,koch,whole-sign,equal,porphyry,regiomontanus,campanus}`.

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

`<skill>/scripts/render_docx.py` is a thin Python wrapper that spawns `node <skill>/scripts/lib/render_docx.js`, piping the chart payload (`{kind, chart, style, interpretation?}`) on stdin. The Node side uses `docx@9.x` and `marked@18.x` (project-local via `<skill>/package.json` — not global) because docx-js has no maintained Python port and the spec's validation path lives in the JS ecosystem (§10.2). Style tokens live in `<skill>/scripts/lib/style.json` and match spec §10.4 (fonts, hex colors without `#`, point sizes that the Node side doubles to half-points for docx-js).

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
