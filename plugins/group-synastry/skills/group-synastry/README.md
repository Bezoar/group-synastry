# `group-synastry` skill — install & usage

A Claude skill for detailed astrological birth charts, synastry, and
composite charts. Phases 1 + 2 (current) cover Western tropical natal +
synastry + composite + Davison, with Markdown / `.docx` / `.pdf` output.

## Install (Claude Code)

This skill ships as part of a Claude Code plugin marketplace. From a
Claude Code session, add the marketplace and install the plugin:

```
/plugin marketplace add Bezoar/group-synastry
/plugin install group-synastry@group-synastry-marketplace
```

(During local development you can instead point the first command at a clone:
`/plugin marketplace add /path/to/group-synastry`.)

**You usually don't need to install anything by hand** — just ask for a chart
and the skill runs a dependency check (`scripts/check_env.py`), then guides you
through any missing pieces (asking before it installs on your machine). To
check or set up manually:

```bash
python scripts/check_env.py            # report what's present / missing + commands
python -m pip install -r requirements.txt   # the one required package (pyswisseph)
```

For `.docx` / `.pdf` output (Phase 2), install the Node-side dependency
project-locally from this directory:

```bash
npm install
```

`.pdf` output additionally requires LibreOffice (`soffice`). The Claude.ai
sandbox has it on PATH; on macOS/Linux dev machines, install LibreOffice
and either expose `soffice` on PATH or rely on the renderer's fallback
search (which checks `/Applications/LibreOffice.app/Contents/MacOS/soffice`
and common Linux paths).

The skill runs without external network access. Asteroid bodies (Chiron,
Ceres, Eris) fall back to bundled Keplerian elements when Swiss
Ephemeris asteroid files (`seas_*.se1`, `s136199s.se1`) aren't installed —
and `seas_18.se1` is bundled in this skill's `ephe/` directory, so Chiron,
Ceres, Pallas, Juno, and Vesta default to arcminute precision out of the
box.

### Chiron accuracy and `seas_18.se1`

Chiron's orbit is heavily perturbed by Saturn, so a single Keplerian
element set cannot do better than **±1–2° accuracy** over multi-decade
ranges. Ceres and Eris remain accurate to arcminutes via the fallback,
but Chiron does not.

For arcminute Chiron precision, install the Swiss Ephemeris asteroid
file `seas_18.se1` (~250 KB):

```bash
mkdir -p ~/.swisseph
curl -o ~/.swisseph/seas_18.se1 https://www.astro.com/ftp/swisseph/ephe/seas_18.se1
export SE_EPHE_PATH=~/.swisseph    # or set in ~/.bashrc / ~/.zshrc
```

`pyswisseph` will pick up the file automatically and the skill's
`lib/ephem.py` wrapper will prefer Swiss Ephemeris over the Keplerian
fallback. The same file also covers Ceres, Pallas, Juno, and Vesta. For
Eris, additionally fetch `s136199s.se1` from the same directory.

Without these files, the skill works correctly but the chart-output
footer notes the Keplerian fallback in use and its accuracy limit.

## Install (Claude.ai)

Upload the contents of this directory (the skill bundle —
`plugins/group-synastry/skills/group-synastry/` in the source repo) as a
skill bundle. The skill auto-detects the `/mnt/user-data/{uploads,outputs}`
layout and reads/writes `people.json` accordingly. On first use, if no
`people.json` has been uploaded, the skill creates a fresh one in
`/mnt/user-data/outputs/` and asks the user to save it locally for re-upload
next session.

## Quick test

From the source repo root:

```bash
cd plugins/group-synastry/skills/group-synastry
python -m pytest tests/ -q
```

The suite should pass. The renderer tests skip automatically if Node and/or
LibreOffice are not installed. The chart tests validate natal positions
for the canonical reference subjects (Alex, born 1988-06-15 Chicago IL;
Jordan, born 1991-02-09 Denver CO) against Swiss Ephemeris reference values
within ±1–10 arcminutes (looser tolerance for asteroid Keplerian
fallback and angle calculations).

## Run a chart

```bash
# Add Alex
python scripts/db.py add --json '{
  "display_name": "Alex",
  "birth": {"date": "1988-06-15", "time": "08:20",
            "tz": "America/Chicago",
            "lat": 41.8781, "lon": -87.6298,
            "place_label": "Chicago, IL",
            "time_accuracy": "exact"}
}'

# Western tropical natal (Markdown)
python scripts/chart.py natal alex

# Same chart as .docx (requires `npm install` in this directory)
python scripts/chart.py natal alex --json | python scripts/render_docx.py -o alex.docx

# Same chart as .pdf (requires LibreOffice)
python scripts/chart.py natal alex --json | python scripts/render_pdf.py -o alex.pdf
```

See `SKILL.md` (sibling file) for the full behavior contract and the spec at
`docs/specs/primary.md` (in the marketplace repo root) for the design rationale.

## Privacy

`people.json` is plain JSON, not encrypted. Birth data (date / time /
place) can be sensitive — it's used for astrology but is also a hint at
identity. Treat the file like other personal data on your machine. v1
ships plaintext intentionally; encryption is in spec §15 as a deferred
question.
