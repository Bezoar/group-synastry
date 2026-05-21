# group-synastry

A Claude skill for computing detailed astrological birth charts and synastry/composite charts for a small private group of people, across multiple astrological systems (Western tropical, Vedic/Jyotish, Hellenistic, Chinese BaZi, Draconic, Heliocentric).

## Status

**Phases 1 & 2 built.** Western tropical natal + synastry + composite + Davison + Markdown (Phase 1) plus `.docx` (via Node + docx-js) and `.pdf` (via LibreOffice headless) rendering (Phase 2). 103/103 tests passing. See `plugins/group-synastry/skills/group-synastry/README.md` for install + run instructions and `plugins/group-synastry/skills/group-synastry/SKILL.md` for the behavior contract. Phases 3–6 (Vedic/Hellenistic/BaZi, predictive, group ops, polish) remain deferred per spec §11.

## Repository Layout

```
group-synastry/
├── .claude-plugin/
│   └── marketplace.json      Marketplace manifest (lists the plugin)
├── plugins/
│   └── group-synastry/
│       ├── .claude-plugin/
│       │   └── plugin.json   Plugin metadata (name, version, author, license)
│       └── skills/
│           └── group-synastry/  The skill bundle (SKILL.md + scripts/ + tests/ + ephe/)
├── docs/
│   ├── specs/primary.md      Authoritative current-state spec (read this first)
│   └── spec.md               Original Phase 1 design spec (historical)
├── evals/
│   ├── README.md             Eval suite overview and how-to-run
│   ├── trigger-evals.json    Description-optimization eval set
│   ├── behavioral-evals.json End-to-end test cases with discriminating assertions
│   └── reference-charts.json Validated reference positions for assertion checking
└── LICENSE                   AGPL-3.0 (forced by bundled Swiss Ephemeris data)
```

## Quick Links

- **Primary (current) spec:** [`docs/specs/primary.md`](docs/specs/primary.md) — authoritative description of the repo as it stands today.
- **Original Phase 1 design spec:** [`docs/spec.md`](docs/spec.md) — frozen, historical context.
- **Eval suite README:** [`evals/README.md`](evals/README.md)
- **Coverage matrix:** see eval README §"Coverage Matrix"

## Key Design Decisions (frozen for v1)

These are documented fully in the spec but worth surfacing upfront:

- **Both Claude Code and Claude.ai supported** — same skill bundle, environment-aware path resolution
- **Pick-and-choose at invocation** — never run "everything" by default
- **Database stored as JSON** at `~/.config/group-synastry/people.json`
- **IANA timezone names required** — historical DST handled correctly via Python `zoneinfo`
- **Always-included bodies** — Sun through Pluto, Chiron, Lilith (Mean Apogee), Ceres, Eris, True Node, ASC, MC
- **Clarification-first behavior** — the skill must ask before computing when meaningful choices exist

## Implementation Plan

Phased rollout per spec §11:

1. **Phase 1** ✓ Foundation/MVP: Western tropical natal + synastry + composite + Davison + Markdown output
2. **Phase 2** ✓ Output polish: `.docx` (via Node `docx` lib) and `.pdf` (via LibreOffice headless)
3. **Phase 3** — Multi-system: Vedic, Hellenistic, Chinese BaZi
4. **Phase 4** — Predictive: progressions, transits, Solar Returns, Vedic dasha, ZR, BaZi luck pillars
5. **Phase 5** — Group operations: compatibility matrices, batch synastry
6. **Phase 6** — Polish: fixed stars, expanded asteroid library, locational

## Dependencies

- **Python 3.10+** with `pyswisseph >= 2.10` (Swiss Ephemeris)
- **Node.js 20+** with `docx@9.x` (for `.docx` output)
- **LibreOffice** (system, for `.pdf` conversion)
- Bundled JPL Keplerian orbital elements for centaurs/asteroids/TNOs as fallback when Swiss Ephemeris asteroid files are unavailable

## License

**AGPL-3.0-only.** See `LICENSE` for the full text.

This repository bundles the Swiss Ephemeris asteroid file
`plugins/group-synastry/skills/group-synastry/ephe/seas_18.se1`. The Swiss
Ephemeris (© Astrodienst AG) is **dual-licensed**: it may be redistributed
*either* under the GNU Affero General Public License, version 3, *or* under a
paid Swiss Ephemeris Professional License. This project takes the AGPL option —
the only license under which the ephemeris data may be redistributed for free.
Bundling that AGPL-licensed data makes the entire combined work AGPL, so the
skill code is released under the same terms. AGPL-3.0 is therefore not merely
*compatible* with redistributing the ephemeris data — it is the license the
ephemeris itself grants for free redistribution.

The version is pinned to **AGPL-3.0-only** (not "or-later") because the
upstream Swiss Ephemeris license (`…/ephe/NOTICE`) references AGPL version 3
specifically and does not extend an "or any later version" option to the
bundled data; pinning to v3.0 keeps the combined-work license faithful to what
upstream actually grants.

If you remove `seas_18.se1` and rely solely on the built-in Moshier ephemeris
and the bundled JPL Keplerian elements, the AGPL obligation that flows from the
Swiss Ephemeris data no longer applies to your derivative — but this repository
as published is AGPL-3.0-only as a whole.
