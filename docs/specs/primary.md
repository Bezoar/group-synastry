# `group-synastry` — Primary Specification

**Status:** Current as of 2026-05-12 (Phase 1 + Phase 2 + Phase 1.5 interpretation)
**Supersedes:** `docs/archive/original-spec/spec.md` — fully. That document's still-relevant content has been folded into this one (decision log §9, user stories §4.4, edge cases §15, algorithmic references §16); the archive is kept only as a frozen historical record.

This document is the authoritative description of the `group-synastry` repository **as it exists today**. It covers what the skill does, how the code is organized, why the load-bearing design decisions were made, and where the seams are for future work. New contributors and future Claude sessions should read this first.

---

## 1. Purpose

`group-synastry` is a Claude skill — packaged as a Claude Code marketplace plugin — that maintains a small private database of people's birth data and produces detailed astrological computations and reports from it. The current scope:

- **Individual natal charts** in the Western tropical system, with all bodies from spec D6 (Sun–Pluto, Chiron, Lilith, Ceres, Eris, True Node, ASC, MC, etc.).
- **Synastry** between any two people in the database, including cross-aspects and bidirectional house overlays.
- **Composite charts** by both algorithms — midpoint composite (per-pair shorter-arc) and Davison (a real chart cast for the temporal + spatial midpoint of the two births).
- **Output to Markdown, `.docx`, or `.pdf`**, with light/dark themes; PDFs default to dark.
- **Optional LLM-authored interpretation prose** at `none / min / max` depth, appended after the data tables.
- **Persistent default output directory** so chart artifacts can be routed automatically into a synced cloud folder (e.g., Proton Drive).

The original non-goals still apply: no real-time/mundane/horary/electional/astrocartography, no GUI, no multi-user cloud storage.

## 2. Repository topology

```
group-synastry-private/
├── .claude-plugin/marketplace.json    Lists the plugin(s) in this repo
├── plugins/
│   └── group-synastry/
│       ├── .claude-plugin/plugin.json Plugin metadata (name, version, author, AGPL-3.0)
│       └── skills/
│           └── group-synastry/        The skill bundle (see §3)
├── docs/
│   ├── archive/original-spec/spec.md  Original Phase 1 design spec — frozen for historical reference
│   └── specs/primary.md               THIS FILE — authoritative current-state spec
├── evals/                             Trigger + behavioral eval suite (see evals/README.md)
├── CLAUDE.md                          Day-to-day operating notes for Claude Code sessions
├── README.md                          Repo overview + install pointer
├── LICENSE                            Full AGPL-3.0 license text
└── .gitignore                         Ignores people.json / settings.json / *.se1 (seas_18.se1 is force-added past it via `git add -f`)
```

The marketplace pattern (`.claude-plugin/marketplace.json` listing plugins under `plugins/<name>/`) is forward-compatible with adding a second plugin later, even though there's only one today. Installation is one command in a Claude Code session: `/plugin marketplace add <repo>` + `/plugin install group-synastry`.

The skill bundle is referred to as `<skill>/` throughout this document — that resolves to `plugins/group-synastry/skills/group-synastry/`.

## 3. The skill bundle

```
<skill>/
├── SKILL.md                The behavior contract Claude follows at runtime
├── README.md               Install + usage instructions
├── requirements.txt        The one core Python dep (pyswisseph>=2.10)
├── package.json            Node-side deps (docx@^9, marked@^18) — project-local
├── package-lock.json       Pinned Node versions
├── ephe/
│   ├── NOTICE              Swiss Ephemeris attribution
│   └── seas_18.se1         Bundled asteroid file (forces AGPL on the bundle)
├── scripts/                (also __init__.py here and in lib/ — package markers)
│   ├── db.py               CRUD on people.json + cohorts
│   ├── chart.py            Western tropical natal chart computation
│   ├── synastry.py         Pairwise synastry
│   ├── composite.py        Midpoint + Davison composites
│   ├── time_range.py       Birth-time hysteresis + time-range variants (§7.6)
│   ├── check_env.py        Dependency doctor (§13.1)
│   ├── render_md.py        Markdown renderer
│   ├── render_docx.py      .docx renderer (Python wrapper for the Node side)
│   ├── render_pdf.py       .pdf renderer (calls render_docx then soffice)
│   └── lib/
│       ├── env.py          Environment detection + outputs dispatcher
│       ├── ephem.py        Swiss Ephemeris wrapper with strict per-body sources
│       ├── kepler.py       JPL Keplerian fallback for Eris, etc.
│       ├── orbital_elements.py
│       ├── formatting.py   Degree formatting + sign glyphs
│       ├── tz.py           IANA-only timezone resolution
│       ├── settings.py     User preferences in settings.json
│       ├── style.json      Style tokens (fonts, sizes, light/dark themes)
│       └── render_docx.js  Node-side docx-js renderer
└── tests/
    ├── conftest.py         Path injection so tests can import scripts modules
    ├── fixtures/
    │   └── people_test.json     Alex + Jordan reference fixtures
    ├── test_chart.py
    ├── test_db.py
    ├── test_settings.py
    ├── test_synastry_composite.py
    ├── test_cohorts.py
    ├── test_time_range.py
    ├── test_check_env.py
    ├── test_render_docx.py
    ├── test_render_pdf.py
    └── test_interpretation_persistence.py
```

## 4. Behavioral contract (what Claude does)

The behavioral contract lives in `<skill>/SKILL.md`. Three principles are load-bearing:

### 4.1 Clarify before computing

When the user hasn't already specified, Claude **must ask** about:

- Which astrological system (Western tropical default; Vedic / Hellenistic / BaZi deferred — §10).
- Output format (inline Markdown default; `.docx`, `.pdf`).
- Target date (for any predictive request).
- House system (Placidus default).
- **Interpretation depth** — every chart request offers `none / min / max`, presented as an `AskUserQuestion`. Skip only if `settings.default_interpretation_level` is set or the user already named a level.

Max two questions per turn; default the rest with a brief inline note. Skip clarification entirely when the user has already given specifics, is iterating on a recent result, or `settings.json` covers the choice.

### 4.2 Pick-and-choose at invocation

There is no "do everything" report. If the user asks for "Alex's chart" without specifying a system, Claude asks. Predictive features are never auto-included.

### 4.3 D6 — always-included bodies

Every natal chart and synastry **must** include: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, **Chiron**, **Lilith (Mean Apogee)**, **Ceres**, **Eris**, True Node, ASC, MC. Missing any is a spec failure — the behavioral evals check this explicitly.

### 4.4 Representative user requests

The canonical phrases the skill triggers on (kept in sync with the eval set). Items marked *(deferred)* are spec'd but not built yet (§10) — when one fires today, say what's available now and offer an inline approximation rather than pretending it works.

- **People management** — "Add Alex to my group: born June 15 1988, 8:20 AM, Chicago IL (41.88°N, 87.63°W)"; "Show me everyone in the group"; "Update Alex's birth time to 1:46 PM"; "Remove the entry for X"; "Tag Alex and Jordan as family" (cohorts, §7.5).
- **Individual charts** — "Show me Alex's full Western chart"; "Compute Alex's Vedic chart" *(deferred)*; "Make a BaZi reading for Jordan" *(deferred)*; "Give me Alex's Hellenistic Lots" *(deferred)*; "What are Jordan's declinations?" *(deferred)*.
- **Synastry / composite** — "Synastry between Alex and Jordan"; "Composite chart for Alex and Jordan"; "Davison chart for Alex and Jordan"; "Make a Word doc / PDF of the synastry between Alex and Jordan".
- **Predictive (individual)** *(all deferred — Phase 4)* — progressions, current Vedic dasha, Solar Return, current transits to natal.
- **Group operations** *(deferred — Phase 5)* — "Compatibility matrix for everyone"; "Synastry between Alex and everyone else".
- **Selectivity (always).** The user must be able to specify *which* system and *which* output format. Default to inline Markdown unless `.docx`/`.pdf` is asked for. See §4.2.

## 5. Computation architecture (the Python core)

### 5.1 Environment dispatch — `lib/env.py`

The same skill bundle runs in Claude Code (where the user's home is on disk) and on Claude.ai (where the only writable directory is `/mnt/user-data/outputs`). `env.py` detects which environment it's running in and returns the right paths for:

- `people_json_path()` — the database
- `settings_json_path()` — user preferences
- `outputs_dir()` — where rendered charts land
- `swisseph_data_paths()` — search path for `.se1` files

(Plus the helpers those build on: `data_dir()`, `is_claude_ai()`, and `swisseph_path_string()`.)

`outputs_dir()` consults `settings.default_output_dir` first, so users can route output to a synced cloud folder (typical Proton Drive path: `~/Library/CloudStorage/ProtonDrive-<email>/group-synastry/charts/`).

**Never hard-code a path** in any other script — always call into `env.py`. Adding a new file type means extending `env.py`, not branching in callers.

### 5.2 Strict per-body ephemeris source — `lib/ephem.py`

The wrapper declares a **best source** per body (`_BODY_SOURCES` dict) and **raises `EphemerisFileMissing`** rather than silently degrading to the Keplerian fallback. Sources:

- `swisseph_builtin` — works without any files; arcsecond accurate for Sun/Moon/planets/True Node/Mean Lilith.
- `swisseph_with_seas18` — uses the bundled `<skill>/ephe/seas_18.se1`; arcsec-arcmin accurate for Chiron / Ceres / Pallas / Juno / Vesta.
- `keplerian_jpl_j2000` — JPL J2000 osculating elements via `lib/kepler.py`; arcminute accurate for Eris (no bundled Swiss Eph file for asteroid 136199).

Pallas, Juno, and Vesta have `seas_18` sources declared in `_BODY_SOURCES` but are **not** in the default natal set (`NATAL_BODIES`) — they're wired up for future use, not computed by any chart today.

**Why this matters:** earlier in development, silent fallback produced different positions on different machines depending on which `.se1` files happened to be installed. Eval results were non-reproducible. Now `force_source="..."` is required to opt into a fallback — silence is no longer allowed.

The Chiron M₀ correction (the original design carried a 2012-era epoch value mislabeled as J2000) is the reason Chiron is now computed via Swiss Ephemeris (bundled `seas_18.se1`) rather than the Keplerian fallback. Reference positions are pinned in `evals/reference-charts.json` against Swiss Eph 2.10 values.

### 5.3 IANA-only timezones — `lib/tz.py`

`normalize_tz()` rejects abbreviations like `EDT`/`PST` and points the user at the IANA equivalent. The abbreviation table is **curated**, not auto-substituted, because the same abbreviation maps to different IANA zones depending on the location (e.g., EST in Indiana is `America/Indiana/Indianapolis`, not `America/New_York`). `to_julian_day_ut()` uses `zoneinfo` for historically correct DST resolution.

### 5.4 The three computation scripts

- **`chart.py natal <id>`** — Western tropical natal chart. Includes all D6 bodies **plus a derived South Node** (always added opposite the True Node), Placidus houses by default, aspects between bodies **and to the Ascendant/Midheaven** with default per-aspect orbs (`lib/formatting.aspect_from_separation`), retrograde markers, per-body source labeling. `--house-system` accepts `placidus|koch|whole-sign|equal|porphyry|regiomontanus|campanus` — validated in `lib/ephem.HOUSE_SYSTEM_CODES`, **not** by an argparse `choices=`, so an unrecognized value errors at computation time rather than at parse time. `--json` emits the canonical structured form for renderer consumption.
- **`synastry.py <a> <b>`** — pairwise inter-aspects (tightest first) **plus** house overlays in *both* directions (A's planets in B's houses, and B's planets in A's). Missing either direction is incomplete (§16, house overlay); the behavioral evals enforce this.
- **`composite.py midpoint <a> <b>` / `composite.py davison <a> <b>`** — midpoint uses per-pair shorter-arc longitudes with equal-house from the composite Ascendant; Davison casts a real natal chart at the temporal + great-circle spatial midpoint and reuses `compute_natal`.

All three resolve `--house-system` through `settings.default_house_system()` (falling back to Placidus when unset) and accept `--interpretation FILE` (since Phase 1.5; see §7).

## 6. Rendering architecture

The skill outputs three formats. Markdown is the inline default; `.docx` and `.pdf` are produced via a Python ↔ Node bridge plus LibreOffice.

### 6.1 Markdown — `scripts/render_md.py`

Pure Python; the chart computation scripts call into it directly. Produces clean Markdown with sign glyphs, aspect symbols, and per-table rendering of angles, planets, and aspects. Exposes `render_natal`, `render_synastry`, `render_composite`, plus `render_interpretation(interp_dict)` (added in Phase 1.5) that emits `## Interpretation` + section h3s.

### 6.2 `.docx` — `scripts/render_docx.py` + `scripts/lib/render_docx.js`

The Python wrapper spawns `node lib/render_docx.js` per call, piping the payload `{kind, chart, style, theme?, interpretation?}` as JSON on stdin. The Node side uses `docx@^9` (project-local, not global) to build the document, applies the style tokens (with theme resolution), and writes the `.docx` to the path the wrapper hands it. (The user-facing flag on `render_docx.py` / `render_pdf.py` is `--output` / `-o`; `--out` is the internal flag the wrapper passes to the Node process.) **Why Node:** `docx-js` has no maintained Python port, and the document-validation tooling lives in the JS ecosystem.

The Node renderer:

- Auto-detects kind from payload shape if `kind` is not set (`overlays_a_in_b` → synastry, `method` + `points` → composite, `planets` + `display_name` → natal).
- Emits a title page paragraph + body/UT metadata, then per-section tables for Angles, Planets, and Aspects.
- Appends interpretation sections (see §7) after the data tables.
- Adds a centered footer with page numbers.
- Applies `Document.background` for theme page color and explicit text colors throughout so the PDF export preserves both.

### 6.3 `.pdf` — `scripts/render_pdf.py`

Produces a `.docx` first (via `render_to_docx`) into a temp directory, then runs `soffice --headless --convert-to pdf --outdir <tempdir> <docx>` and moves the result to the requested output path. `locate_soffice()` checks PATH first, then falls back to `/Applications/LibreOffice.app/Contents/MacOS/soffice` (macOS), `/usr/bin/libreoffice` (Linux), and a few other common paths. The Claude.ai sandbox has `soffice` on PATH already.

### 6.4 Style tokens + themes — `scripts/lib/style.json`

Centralized style tokens, with two themes:

- **light** — black-on-white; standard for print and editing. Default for `.docx`.
- **dark** — `1A1A24` page background, `E8E6F0` body text (hex is stored without a leading `#` in `style.json`), periwinkle headings, gold accents. Default for `.pdf` (PDFs are typically viewed on-screen).

Both renderers accept `--theme {light,dark}` to override. The page background is the load-bearing mechanism for dark PDFs — docx-js writes `<w:background w:color="1A1A24"/>` into `word/document.xml`, and LibreOffice's PDF export preserves it. A regression test (`test_dark_theme_pdf_is_actually_dark`) uses ImageMagick to confirm the rendered PDF has mean brightness <100 on the dark theme vs >180 on light.

## 7. The interpretation system (Phase 1.5)

Chart computation is deterministic. Interpretation prose is not. The skill treats interpretation as a separate, optional layer:

### 7.1 LLM-authored, not skill-authored

The Python scripts emit no prose. When the user asks for `min` or `max` interpretation, **Claude writes the prose** in the conversation, structures it as a JSON object, and feeds it to the renderers. This trades consistency (different runs produce different phrasings) for contextual quality (each section can reference specific chart features). The alternative — a stock interpretation library in `references/*.md` — is documented as a future extension (§14) but not built.

### 7.2 Payload shape

```json
{
  "sections": [
    {"heading": "Sun in Taurus, 7th house",
     "body": "Markdown with **bold**, *italic*, [links](https://...), lists, and (future) ![images](url)."},
    ...
  ]
}
```

Section bodies are markdown — parsed at render time. The renderer is **level-agnostic**: it just emits whatever sections it gets. "Level" (`none / min / max`) is purely a behavioral signal to Claude about how many and how long each section should be. SKILL.md §"Generating interpretation" specifies:

- `none` → no `interpretation` argument; data tables only.
- `min` (~500 words) → 3–5 sections covering Sun, Moon, Ascendant, and the three tightest aspects.
- `max` (~2500–4000 words) → one section per planet (in sign + house), one section per major aspect, sections for retrograde planets / nodes / asteroids, and a closing synthesis covering element / modality balance and chart shape.

The `none / min / max` question is **suppressed when `settings.default_interpretation_level` is set** — users who consistently want one depth can configure it once and skip the AskUserQuestion every time. Future work (noted in §14) is a continuous slider replacing the three-button choice; the renderer is already shape-agnostic, so that's a SKILL.md change rather than a code change.

Future work: a continuous slider replacing the 3-button question. The renderer is already shape-agnostic, so this is a SKILL.md-only change.

### 7.3 Markdown body rendering

For `.docx` / `.pdf`, the Node renderer (`lib/render_docx.js`) uses `marked.Lexer` to walk the markdown AST and emit docx-js paragraphs, lists, and `ExternalHyperlink`s. In-body headings are forced to h3 so the section's h2 stays dominant. Image tokens currently render as `[image: alt]` placeholders — future media-link support extends the `image` token case in `inlineRuns()` to fetch and embed binary data.

For Markdown output (`chart.py natal alex --interpretation interp.json`), `render_interpretation()` emits `## Interpretation` + per-section `### Heading` + body verbatim. The body is already markdown.

### 7.4 Source persistence — the sidecar

When `render_docx.py` / `render_pdf.py` is given `--interpretation`, it writes `<output_stem>.interpretation.md` alongside the rendered document. The sidecar is a human-editable markdown file:

```markdown
# Interpretation: Alex — Natal

_Auto-generated by the group-synastry skill alongside `alex.pdf`. Edit
the body markdown freely and re-render with
`--interpretation alex.interpretation.md` to update the document._

## Sun in Taurus, 7th house

Body markdown here...

## Moon in Virgo, 11th house

Body markdown here...
```

The format round-trips: `parse_interpretation_file()` accepts either `.json` (the canonical machine-readable shape) **or** `.md` (the sidecar format), so the workflow is render → sidecar → edit → re-render. `--no-sidecar` suppresses the sidecar emission for one-off renders where the user doesn't want a sibling file.

### 7.5 Data always comes before prose

This is enforced by the renderer (`buildDocument` appends interpretation **after** `children = renderNatal(...)` etc.) and pinned by `test_interpretation_renders_after_data_with_markdown_formatting`, which asserts the byte offset of "Notable Aspects" precedes the byte offset of "Interpretation" in `document.xml`. The rationale: some users only want the numbers. They should be able to stop scrolling at the Aspects section without losing anything.

## 7.5. Cohorts and folder layout (Phase 3 — issue #9)

A **cohort** is a named group of people that share astrological lore. The DB (`people.json` v2) carries the structural membership; cohort prose lives outside the DB so it can be shared with cohort members.

### Schema v2

```json
{
  "version": 2,
  "people": [...],
  "cohorts": [
    {
      "id": "lumina",
      "display_name": "Lumina",
      "description": "Family/inner circle",
      "created_at": "2026-05-13T...",
      "members": ["alex", "jordan", "casey"]
    }
  ]
}
```

`load()` reads both v1 (no `cohorts` key) and v2 transparently. The first `save()` after upgrading the code upgrades the file in place (writes v2 with `cohorts: []`).

### Folder layout convention

```
<output-root>/
├── archive/                frozen snapshots from pre-cohort layout
├── people/                 people.json lives here when people_db_dir is set
└── cohorts/
    └── <cohort-id>/
        ├── birth-charts/   natal PDFs (duplicated across cohorts when a person belongs to multiple)
        ├── synastry/       pair charts (synastry + composite + Davison)
        └── notes.md        shared cohort prose lore — markdown; supports future media embeds
```

Duplication of birth charts across cohorts is deliberate (cheap storage, simpler share semantics). Sharing happens at the cohort folder level — `people/` stays private.

### Routing layers

`resolve_output_path(path_arg, kind, cohort, time_range_pair, time_range_label)` applies (when `path_arg` is a bare filename):

1. **Cohort prefix.** If `cohort` is passed or `settings.active_cohort` is set, prepend `cohorts/<id>/`. Per-call `cohort` wins over the setting.
2. **Time-range prefix.** If BOTH `time_range_pair` (e.g. `alex+casey`) AND `time_range_label` (e.g. `casey-1700`) are passed, append `time-range/<pair>/<label>/` next. When this layer is active, the kind subfolder layer below is **skipped** so all chart kinds for a variant share a folder.
3. **Kind subfolder.** Otherwise, if `settings.default_output_subfolders[kind]` exists, append it.

Any layer can be inactive without breaking the others. Explicit subdirs in `--output` and absolute paths bypass *all* layers.

### CLI

`db.py cohort {list, show <id>, add --json <obj>, update <id> --json <patch>, remove <id>, add-member <cohort> <person>, remove-member <cohort> <person>, set-active <id>, migrate --name <id> [--display <name>] [--description <text>]}`. Render commands accept `--cohort <id>` to override `active_cohort` for one invocation, and `--time-range-pair`/`--time-range-label` for time-range routing.

## 7.6 Birth-time hysteresis and time-range charts (issue #12)

### Schema

Person records gain an optional `birth.time_hysteresis_minutes` (non-negative integer; default 0). Semantically the **half-width** of the uncertainty window — a value of `60` means ±60 min, total 2 hours. The field is additive on the v2 schema (no version bump): records without it read as 0; records with explicit 0 are not persisted (kept off-disk to avoid noise). `db.get_hysteresis_minutes(person)` is the read accessor.

Complementary to the existing categorical `birth.time_accuracy` — keep both; the categorical is the hint, the numeric is the quantitative window.

### Strategies

`scripts/time_range.py` exposes three strategies for sampling within the window:

| Strategy | Output |
|---|---|
| `min-max` | 2 variants at window edges (`-hys`, `+hys`) |
| `every-n-minutes` | step through the window; includes both endpoints; `--step` controls resolution |
| `asc-boundaries` | adaptive — bisects the window to find Ascendant sign crossings; samples one variant per resulting sign interval (degrades to one variant at the recorded time if no crossings) |

### Adaptive recommendation UX

The skill's contract (SKILL.md) is to *briefly mention* the hysteresis when generating a chart involving a person who has it set, then — if the user accepts time-range generation — run `time_range.py scan` first. The scan returns Asc longitudes at min/recorded/max and the count of sign-boundary crossings in the window, plus a one-sentence strategy recommendation. The skill then offers the full menu but with one option marked Recommended.

### Folder convention

Variants live at `<output-dir>/cohorts/<cohort-id>/time-range/<pair>/<varied-person-id>-HHMM/`. The leaf folder name combines the varied person's id and the local time of that variant (e.g. `casey-1700` for the 17:00 variant). Per-pair subdirectories use `+` as the separator (`alex+casey`) to distinguish "this is the pair-id" from filename-level `-` separators used elsewhere. All chart kinds for a variant land in the same folder using their normal short-prefix filenames (`cmp-`, `syn-`, `dav-`).

Open question: when both people in a pair have non-zero hysteresis, the leaf naming will need a 2-person convention (e.g. `casey-1700_mark-1340`). Deferred until needed.

### CLI

`time_range.py {list, scan, render} <args>`. The render subcommand drives the whole pipeline: compute the time list, compute and render cmp/syn/dav for each variant in-process, land each under the right time-range folder.

## 8. Persistence model

| Artifact | Lives at | Created by | Notes |
|---|---|---|---|
| People DB | `~/.config/group-synastry/people.json` (Claude Code) or `/mnt/user-data/uploads/people.json` (Claude.ai) | `db.py add/update/remove` | Plain JSON, no encryption (deferred; §14). Birth data is sensitive — treat the file as PII. |
| User preferences | `<data_dir>/settings.json` | `lib/settings.py set` | Known keys: `default_house_system`, `default_ayanamsa`, `default_output_format`, `default_output_dir`, `default_output_subfolders`, `default_interpretation_level`, `default_zodiac`, `people_db_dir`, `active_cohort`. Unknown keys round-trip through saves for forward compat. `default_output_subfolders` is a dict mapping chart kind → subfolder name. `active_cohort` is a cohort id that adds a `cohorts/<id>/` prefix before the kind subfolder when rendering bare-filename outputs. `people_db_dir` overrides the location of `people.json` (defaults to `<data_dir>`); useful for putting the DB in a synced cloud folder while keeping `settings.json` local. |
| Ephemeris file | `<skill>/ephe/seas_18.se1` (bundled) and optionally `~/.swisseph/` (user-provided) | Shipped with the skill | Force-added past `.gitignore`'s `ephe/*.se1` rule. AGPL-licensed by upstream — this is why the whole bundle is AGPL. |
| Rendered chart | `outputs_dir() / <filename>` | `render_docx.py`, `render_pdf.py` | `outputs_dir()` honors `default_output_dir` first. Absolute `--output` paths bypass it. |
| Interpretation sidecar | `<output_stem>.interpretation.md`, next to the rendered file | The renderers, when `--interpretation` is used and `--no-sidecar` is not | Human-editable; re-importable via `--interpretation`. |

Not every key in `KNOWN_KEYS` has a script consumer yet: `default_zodiac` and `default_ayanamsa` are forward-declared for the deferred sidereal/Vedic work (nothing reads them today), and `default_output_format` / `default_interpretation_level` are behavioral hints Claude consults in the clarify-flow (per SKILL.md), not inputs to any CLI. They still round-trip through saves.

## 9. Key design decisions and the reasons for them

| Decision | Rationale |
|---|---|
| **AGPL-3.0-only** for the whole bundle | The bundled `seas_18.se1` is AGPL by upstream; combined distribution inherits. Single license avoids ambiguity. If `seas_18.se1` is ever removed, the skill code itself can be relicensed permissively — the structure supports this. |
| **`docx` is project-local, not global** | `<skill>/package.json` + `<skill>/node_modules/` keeps the skill self-contained inside the marketplace plugin. Uninstalling the plugin doesn't leave globals lying around; multiple skills can use different `docx` versions. |
| **No silent ephemeris fallback** | Earlier behavior — degrade-to-Keplerian when `.se1` files aren't present — produced different positions on different machines, breaking eval reproducibility. Now callers must pass `force_source="keplerian_jpl_j2000"` to opt in. |
| **IANA timezones only; abbreviations rejected** | "EST" maps to multiple IANA zones (Indiana vs. New York have different historical DST). Abbreviation auto-substitution silently produces wrong charts; rejection forces the user to specify. |
| **D6 always-included bodies** | Chiron, Ceres, Lilith, Eris carry interpretive weight that the user probably wants; making them opt-in would let them be silently missed. |
| **Python → Node bridge for `.docx`** | `docx-js` has no maintained Python port; the planned document-validation path lives in the JS ecosystem. Subprocess overhead per render is ~150ms — acceptable. |
| **Data before prose, always** | Honor users who want the numbers without scrolling past interpretation. Pinned by an ordering test (byte index of Aspects < byte index of Interpretation in `document.xml`). |
| **LLM-authored interpretation, not stock library** | Stock interpretations would be more consistent run-to-run but less contextual. Long-term, a hybrid is possible (stock skeleton + LLM synthesis) — `references/*.md` markdown files are planned per spec but not yet built. |
| **`.pdf` defaults to dark; `.docx` defaults to light** | PDFs are usually viewed on-screen; docx files are usually edited or printed. Different defaults match different consumption modes. Both accept `--theme` to override. |
| **`default_output_dir` resolves lazily** | `env.py` imports `settings` inside `outputs_dir()` rather than at module level to avoid a circular import (settings.py imports env.py for path resolution). Lazy import is a deliberate cycle-break. |
| **Sidecar archiving (interpretation source persists)** | Without it, the prose Claude writes is either baked into a binary document (unimportable) or ephemeral (lost when the chat is cleared). The sidecar lets users edit and re-render without re-asking Claude to re-write. |

### Mapping to the original decision log (D1–D9)

The original spec froze nine decisions. They remain authoritative for v1 scope; this is where each one lives now (so the archive isn't needed to look them up):

| # | Original decision | Current state |
|---|---|---|
| D1 | Primary environment: both Claude Code and Claude.ai | Unchanged — `lib/env.py` dispatches between the two (§5.1). |
| D2 | Full predictive toolkit, pick-and-choose at invocation | Pick-and-choose holds (§4.2); the predictive toolkit itself is deferred to Phase 4 (§10). |
| D3 | DB as JSON at `~/.config/group-synastry/people.json` (Claude Code); upload/download on Claude.ai | Holds; path now resolved by `env.py` and overridable via `settings.people_db_dir` (§8). |
| D4 | Default house system: Placidus (per-call configurable) | Unchanged (§4.1, §5.4). |
| D5 | Default Vedic ayanamsa: Lahiri | Stands as the default for when Vedic ships; stored as `settings.default_ayanamsa` (§8). Vedic itself deferred. |
| D6 | Always-included bodies | Unchanged and enforced — see §4.3. |
| D7 | Timezone authority: IANA only | Unchanged — `lib/tz.py` (§5.3). |
| D8 | Geocoding: manual lat/lon by default; Claude may suggest coords via web search | Unchanged. Birth records store explicit `lat`/`lon`; there is no geocoding API integration (the API choice is still an open question, §14). |
| D9 | Privacy: plaintext JSON, no encryption in v1, documented | Unchanged — plaintext, treated as PII (§8); encryption remains deferred (§14). |

## 10. Capabilities matrix

| Capability | Status | Source of truth |
|---|---|---|
| Western tropical natal | ✓ Phase 1 | `chart.py`, `lib/ephem.py` |
| Synastry (cross-aspects + bidirectional overlays) | ✓ Phase 1 | `synastry.py` |
| Midpoint composite (shorter-arc) | ✓ Phase 1 | `composite.py midpoint` |
| Davison composite | ✓ Phase 1 | `composite.py davison` |
| D6 always-included bodies | ✓ Phase 1 | `lib/ephem.py` + behavioral evals |
| IANA-only timezone validation | ✓ Phase 1 | `lib/tz.py` |
| Plain Markdown output | ✓ Phase 1 | `render_md.py` |
| `.docx` output via docx-js | ✓ Phase 2 | `render_docx.py` + `lib/render_docx.js` |
| `.pdf` output via LibreOffice | ✓ Phase 2 | `render_pdf.py` |
| Light/dark themes | ✓ Phase 2 | `lib/style.json` |
| Persistent default output directory | ✓ Phase 2 | `lib/env.py`, `lib/settings.py` |
| Kind-based output subfolder routing | ✓ Phase 2.1 | `lib/settings.subfolder_for_kind`, `render_docx.resolve_output_path` |
| Cohorts (DB schema v2 + folder convention + cohort routing) | ✓ Phase 3 (issue #9) | `db.py cohort` subcommands, `lib/settings.active_cohort`, `lib/env.people_json_path` honoring `people_db_dir` |
| LLM-authored interpretation (`min`/`max`) | ✓ Phase 1.5 | `SKILL.md`, `render_docx.js` markdown walker |
| Markdown body parsing in interpretation | ✓ Phase 1.5 | `marked` lexer + `lib/render_docx.js` |
| Interpretation sidecar (round-trip-able) | ✓ Phase 1.5 | `parse_interpretation_file`, `write_interpretation_sidecar` |
| Vedic / Jyotish | — Phase 3 (deferred) | `references/vedic.md` (not yet built) |
| Hellenistic (Lots, sect, ZR) | — Phase 3 / 4 (deferred) | |
| Chinese BaZi | — Phase 3 (deferred) | |
| Draconic | — deferred (lower priority) | |
| Heliocentric | — deferred (lower priority) | |
| Progressions / transits / returns / dasha | — Phase 4 (deferred) | |
| Group operations (compatibility matrix, batch synastry) | — Phase 5 (deferred) | |
| Fixed stars / asteroid library / locational / harmonics | — Phase 6 (deferred) | |
| Continuous interpretation slider | — future | Renderer already shape-agnostic; SKILL.md-only change |
| Embedded images in interpretation | — future | Extend `image` token in `lib/render_docx.js` `inlineRuns()` |

### 10.1 Intended scope for the deferred systems

When the deferred systems are built, the original design intended this per-operation coverage (preserved here so the intent isn't lost):

| System | Individual | Synastry | Midpoint composite | Davison |
|---|---|---|---|---|
| Western tropical | ✓ built | ✓ built | ✓ built | ✓ built |
| Vedic / Jyotish (sidereal, multi-ayanamsa) | ✓ | ✓ (kuta-style + inter-aspects) | ✗ (not traditional) | ✗ |
| Hellenistic (Whole-Sign, Lots, sect) | ✓ | ✓ (alongside tropical) | rarely meaningful | ✗ |
| Chinese BaZi (Four Pillars) | ✓ | ✓ (element compatibility, animal triads) | ✗ | ✗ |
| Draconic | ✓ | ✓ (alongside tropical) | ✓ | ✓ |
| Heliocentric | ✓ | rarely used | rarely used | ✗ |

Intended predictive subsystems (individual only): secondary progressions, solar arc directions, Solar/Lunar Return, transits-to-natal (Western); annual profections, Zodiacal Releasing from Spirit & Fortune (Hellenistic); Vimshottari Dasha — Maha/Antar/Pratyantar (Vedic); Da Yun 10-year luck pillars (Chinese).

## 11. Extension points

Where to make common changes:

- **New body (planet / asteroid / point):** add to `lib/ephem.py` `_BODY_SOURCES` (with a chosen best source), `_SWE_BODIES` if Swiss Eph–capable, `lib/orbital_elements.py` if Keplerian-only, `lib/formatting.PLANET_GLYPHS`, and the `NATAL_BODIES` / `SYNASTRY_BODIES` / `COMPOSITE_BODIES` tuples in the relevant scripts. Update reference values in `evals/reference-charts.json`.
- **New house system:** add the Swiss Eph code byte to `lib/ephem.HOUSE_SYSTEM_CODES`. Update behavioral evals if it should be offered.
- **New chart kind (e.g., Solar Return when Phase 4 lands):** add a renderer in `lib/render_docx.js`, a detection rule in `detectKind()` and Python `detect_kind()`, and a per-kind `render_<kind>` in `render_md.py`. Add fixtures + tests.
- **New theme:** add an entry under `themes` in `lib/style.json` (e.g., `sepia`). The Node renderer's `resolveStyle()` honors arbitrary theme names.
- **New persistent preference:** add a string to `lib/settings.KNOWN_KEYS` and document it in this spec's §8 table. Add a test to `test_settings.py` if it has runtime effects.
- **New external system (cloud drive, etc.) for output:** typically just point `default_output_dir` at the synced folder. Direct API integration would go in a new `lib/sync_<provider>.py` and a new flag on the renderers.
- **Reference library for interpretation:** create `<skill>/references/*.md` matching the structure SKILL.md anticipates (`vedic.md`, `synastry-aspects.md`, `asteroids-and-points.md`). Claude can read these when authoring interpretation prose to ground stock paragraphs.

## 12. Testing strategy

### 12.1 Reference subjects

`<skill>/tests/fixtures/people_test.json` defines two canonical subjects:

- **Alex** — born 1988-06-15 08:20 America/Chicago, Chicago IL (41.8781°N 87.6298°W).
- **Jordan** — born 1991-02-09 14:45 America/Denver, Denver CO (39.7392°N 104.9903°W).

Their planetary positions, aspects, and synastry contacts are validated against Swiss Ephemeris 2.10 and pinned in `evals/reference-charts.json`.

### 12.2 Tolerance hierarchy

From `evals/README.md` §"Notes on Reference Data Accuracy":

| Quantity | Tolerance |
|---|---|
| Major planet positions | ±1 arcminute |
| Asteroid Keplerian fallback (Ceres, Eris) | ±2 arcminutes |
| House cusps and angles | ±5 arcminutes (sensitive to coordinate precision) |
| Solar Return moment | ±5 minutes |
| Davison location | ±0.5° (great-circle midpoint; tolerance covers coordinate precision) |

A skill that consistently misses by 30+ arcminutes is doing something fundamentally wrong (computing for the wrong date, applying ayanamsa twice, etc.).

### 12.3 Test layering

- **Unit tests** — `test_chart.py`, `test_db.py`, `test_settings.py`, `test_synastry_composite.py`. Fast (<1s each), no external deps.
- **Renderer integration tests** — `test_render_docx.py`, `test_render_pdf.py`. Require Node and (for PDF) LibreOffice. Auto-skip if missing.
- **Interpretation persistence tests** — `test_interpretation_persistence.py`. Cover the `--interpretation` flag on chart scripts, sidecar emission, the round-trip parser.
- **Eval suite** (`/evals`) — broader behavioral and trigger evals; see `evals/README.md`.

Renderer tests skip cleanly on machines without their dependencies, so CI on a barebones runner won't false-fail. (Run `pytest tests/ -q` for the current count rather than relying on a number here — it changes with every feature.)

## 13. Marketplace install and dev setup

### 13.1 End-user install (Claude Code)

```
/plugin marketplace add Bezoar/group-synastry
/plugin install group-synastry@group-synastry-marketplace
```

Dependencies are then handled by a **preflight doctor** rather than manual
steps. `scripts/check_env.py` probes (tiered): Python ≥3.10 + `pyswisseph`
(**core** — blocks all charts), Node + project `node_modules` (`.docx`) and
LibreOffice (`.pdf`) (**optional** — degrade, never block), and the bundled
`seas_18.se1` (**info**). It prints per-gap install commands (targeting the
active interpreter via `sys.executable -m pip`), a parseable `SUMMARY` line,
and exits non-zero iff a core dep is missing. `requirements.txt` pins the one
required package; `lib/ephem.py` wraps `import swisseph` so a missing package
yields an actionable message instead of a bare traceback.

Per SKILL.md §"Dependencies", the skill runs the doctor once per session and:
installs core silently in the ephemeral Claude.ai sandbox but **asks first on a
local machine**; for optional deps, acts only on explicit format requests and
otherwise falls back (Markdown ← `.docx` ← `.pdf`). Manual equivalents:

```bash
python scripts/check_env.py                  # report status + commands
python -m pip install -r requirements.txt    # core (pyswisseph)
cd <skill> && npm install                    # for .docx
# LibreOffice install required for .pdf — see <skill>/README.md
```

### 13.2 Dev setup (this repo)

```bash
python3 -m venv .venv
.venv/bin/pip install pytest pyswisseph
cd plugins/group-synastry/skills/group-synastry && npm install
.venv/bin/python -m pytest tests/ -q
```

Full suite runs in ~3 minutes (mostly soffice-bound PDF tests); the fast suite (excluding `test_render_pdf.py`) runs in <5 seconds.

## 14. Known gaps and open questions

- **Phase 3+ astrology features.** Vedic / Hellenistic / BaZi / predictive / group ops are all spec'd but not built. Phase 3's output volume needs `.docx`/`.pdf` (Phase 2) before it's worth building, which is why Phase 2 came first.
- **Stock interpretation library.** SKILL.md references `references/*.md` files (`synastry-aspects.md`, `asteroids-and-points.md`, etc.) but they don't yet exist. Claude currently draws on training knowledge for all interpretation prose. Building the library would give consistency without sacrificing context (hybrid: stock skeleton + LLM synthesis).
- **Image embedding in interpretation.** `lib/render_docx.js` currently renders `![alt](url)` as `[image: alt]` text. Real embedding needs URL-to-buffer fetching, format detection, and sizing logic. The marked AST already provides the right tokens.
- **Continuous-slider interpretation depth.** The 3-button (none/min/max) AskUserQuestion is what users see today. The renderer is already level-agnostic, so this is a SKILL.md-only swap when ready.
- **Encryption of `people.json`.** Spec §15 leaves this as a deferred question. Currently plaintext; the user is expected to treat the file as PII.
- **Direct cloud API integration.** Output currently flows through synced folders (Proton Drive sync app). A native API integration (Proton Drive REST, Google Drive, Dropbox, etc.) would remove the dependency on the desktop sync client but isn't built.
- **Eval suite vs. current state drift.** The eval JSON files have descriptive prose that references the pre-marketplace `skill/...` paths. This is descriptive (not active config) but slightly stale; cleanup is a future polish task.
- **Group composite over N>2 people.** A midpoint over more than two people ("family chart") may or may not be meaningful. Deferred until requested.
- **Geocoding API choice.** If automatic place→lat/lon lookup is ever wanted, the options are Nominatim (OSM, free), a paid provider (Google Places), or relying on Claude's web search at runtime. Currently the user enters lat/lon (D8); no API is wired in.
- **Computation caching.** The same person's natal chart is recomputed across calls. No cache today — computation is fast enough — but a cache could be added if profiling ever shows it matters.

## 15. Edge cases and error handling

How the skill behaves at the boundaries. This corrects the original spec's §14 table where the implementation has since diverged (notably missing-ephemeris handling, which is now strict rather than a silent fallback):

| Case | Handling |
|---|---|
| Unknown birth time | Compute the chart but omit Ascendant, Midheaven, IC, Descendant, Vertex, and house cusps; sign positions for luminaries/planets remain valid. Print a prominent note. |
| Approximate birth time | Compute as given. If `birth.time_hysteresis_minutes` is set, offer time-range variants (§7.6); the Ascendant moves ≈1°/4 min, so an hour of uncertainty is ≈15° of Ascendant. |
| Pre-1582 (Julian calendar) dates | Accepted; Swiss Ephemeris handles the calendar correctly when given as a Julian Day. Warn the user. |
| Polar latitudes (>66°) | Placidus/Koch can fail to produce cusps; fall back to Whole-Sign and tell the user. |
| Person not found | List the available people and offer to add a new one — never silently guess. |
| Invalid timezone (abbreviation) | Rejected with a pointer to the IANA name (e.g. "use `America/New_York`, not `EST`") — see §5.3. |
| DST fall-back ambiguity | `zoneinfo` resolves the fold deterministically; a user override remains possible via explicit offset in the record. |
| Two people with the same display name | Disambiguate via id (or cohort/tag); `db.find` matches id first, then display name. |
| **Missing Swiss Ephemeris file** | **Raises `EphemerisFileMissing` — no silent Keplerian fallback** (§5.2). This is the deliberate reversal of the original spec, which called for a silent degrade; that produced machine-dependent positions and broke eval reproducibility. A caller must pass `force_source=...` to opt into the fallback. |
| Composite requested with a non-member | Prompt for their birth data; do **not** auto-add to the DB — ask first. |
| LibreOffice unavailable | Skip `.pdf`; offer `.docx` or Markdown and explain (the dependency doctor, §13.1, reports this). |
| Node / `docx-js` unavailable | Skip `.docx`; offer Markdown and explain how to install. |

## 16. Algorithmic references

Where the load-bearing algorithms come from. The built ones cite the implementing module; the deferred ones record the intended approach so a future implementer doesn't have to re-derive them.

| Component | Status / source | Notes |
|---|---|---|
| Tropical chart | ✓ `lib/ephem.py` | `swe.calc_ut` + `swe.houses_ex`. |
| Midpoint composite | ✓ `composite.py` | Per-pair shorter-arc midpoint of the two longitudes; equal-house from the composite Ascendant. |
| Davison composite | ✓ `composite.py` | Real chart cast at the temporal midpoint (UT) and **great-circle** spatial midpoint (the original spec used a naive lat/lon midpoint; upgraded for global cases). |
| Keplerian fallback (Eris, etc.) | ✓ `lib/kepler.py` + `lib/orbital_elements.py` | Solve Kepler's equation E − e·sin E = M iteratively; standard orbit→ecliptic transform from J2000 osculating elements. |
| House overlay | ✓ `synastry.py` | Walk each partner's planets through the other's cusps — **both directions** are required (§5.4). |
| Vedic (sidereal + nakshatra + Vimshottari Dasha) | deferred | `swe.set_sid_mode(SIDM_LAHIRI)` + `FLG_SIDEREAL`; 27 nakshatras × 800′, pada = ¼ subdivision; dasha birth-lord from Moon's nakshatra, balance from position within it. |
| BaZi (Four Pillars) | deferred | Year via Lìchūn cutoff; day pillar via JD-mod-60 from a known anchor; month/hour from year-stem and day-stem rules. |
| Hellenistic Lots / profections / Zodiacal Releasing | deferred | Lot of Spirit = ASC + Sun − Moon (day chart); profection = (age mod 12)+1 whole-sign from ASC; ZR L1 in years, L2 in months. |
| Solar arc / secondary progression | deferred | Solar arc = whole chart + (progressed Sun − natal Sun); secondary = recompute at natal JD + years-elapsed days. |

## 17. Related documents

- **`<skill>/SKILL.md`** — the behavior contract Claude follows at runtime. Update this when changing user-facing behavior. Structurally it is kept under ~400 lines and covers, in order: environment detection → DB read → request-type identification → **clarify** → run the right script → render; plus the load-bearing principles (clarify-before-computing §4.1, pick-and-choose §4.2, when-to-ask-vs-proceed, dependencies, and when to consult `references/*.md`). Detailed interpretation guidance lives in `references/` files (planned) that load only when relevant, not in SKILL.md itself.
- **`CLAUDE.md`** (repo root) — day-to-day operating notes for Claude Code sessions in this repo. Points at this spec.
- **`docs/archive/original-spec/spec.md`** — the original Phase 1 design spec. **Fully superseded by this document** — its still-relevant content (decision log D1–D9, user stories, edge cases, algorithmic references, intended system scope) has been folded in above, so you should not need to open it. Kept only as a frozen historical record of the initial design; its internal paths and the silent-fallback edge case are stale.
- **`evals/README.md`** — eval suite design philosophy and run instructions. The coverage matrix tells you which behavior each eval pins.
- **`evals/reference-charts.json`** — ground-truth positions for Alex and Jordan. Only change when the underlying ephemeris improves.

---

When this spec drifts from the code (it will, eventually), update this file first, then the affected behavioral evals, then `CLAUDE.md` operational notes, in that order.
