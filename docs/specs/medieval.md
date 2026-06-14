# `group-synastry` — Medieval / Traditional European astrology (design spec)

**Status:** Design spec for the Phase 3 medieval / traditional European track.
**Increment 1 — the deterministic substrate — is now built**: sect, essential
dignities (+ almuten), the Lots of Fortune & Spirit, and Alcabitius houses, via
`lib/medieval.py`, the `medieval.py natal` CLI, and Markdown rendering. The
interpretation/citation layer (§5) and the remaining techniques in §3 are **not
yet built**. The authoritative description of the repository *as it exists
today* remains [`primary.md`](primary.md). See §3.1 for the built/deferred split.
**Date:** 2026-05-24 (increment 1 built 2026-05-25)
**Background:** the scoping analysis and decision log behind this spec is
[`../research/phase-3-medieval.md`](../research/phase-3-medieval.md).

---

## 1. Scope and intent

Add **medieval / traditional European astrology** as a system alongside the
Western tropical core. Settled scope:

- **Era anchor** — the broad **"traditional" band**, treated continuously: Latin
  medieval (e.g. Bonatti), the Perso-Arabic sources it translated (Masha'allah,
  Abu Maʿshar, Sahl), and the Renaissance tail (e.g. Lilly).
- **Depth** — **everything**: natal charts, synastry, and returns, plus the
  predictive / time-lord layer (firdaria, profections, solar revolutions).
- **Zodiac** — tropical (no sidereal conversion).
- **Houses** — **Alcabitius** by default (Swiss Ephemeris house code `B`); other
  house systems may be added later.

It is best understood as an **enriched superset of the Hellenistic substrate**
(lots, sect, profections, triplicities) extended with Perso-Arabic and later
material (firdaria, expanded lots, lunar mansions, fuller dignity scoring,
Alcabitius houses, primary directions). It is kept a **separate track** from the
planned Hellenistic system for now; the two may later merge into a single
continuous European-astrology track.

## 2. Why it fits (computational reuse)

The accuracy-critical part — precise planet / house / angle positions — is
**already solved** by the Swiss Ephemeris layer. Medieval astrology is tropical,
uses Alcabitius houses (already supported), and `swe_fixstar` covers fixed stars.
Almost everything medieval-specific is **deterministic arithmetic and lookup
tables layered on positions already computed** — not model-generated values.

## 3. Techniques in scope

Most are deterministic given positions; effort notes flag the exceptions.

| Technique | Notes |
|---|---|
| **Essential dignities** — domicile, exaltation, triplicity, term/bound, face/decan; detriment/fall; almuten of a degree | Lookup tables + scoring |
| **Sect** — diurnal/nocturnal, sect light, benefic/malefic of the sect, *hayz* | Deterministic |
| **Lots / Arabic Parts** — Fortune, Spirit, and the wider catalogue; day/night reversal | Longitude arithmetic |
| **Triplicity rulers** — day / night / participating | Table |
| **Profections** — annual and monthly; lord of the year | Arithmetic |
| **Firdaria** — Persian planetary periods and sub-periods | Period tables |
| **Solar revolutions (returns)** — chart cast at the return moment | Reuses natal computation |
| **Lunar mansions** — the 28 manzil | Boundary table |
| **Reception, antiscia / contra-antiscia, planetary hours, planetary moieties/orbs** | Arithmetic / tables |
| **Fixed stars** — Behenian set and contacts to chart points | `swe_fixstar` + star natures |
| **Temperament** | Rule synthesis |
| **Hyleg / alcocoden, almuten figuris** | Variant rules across authors |
| **Primary directions** | **Deferred** — the one genuinely high-effort piece (spherical trig, multiple conventions); tracked as separate work |

### 3.1 Implementation status

**Built (increment 1, `lib/medieval.py` + `medieval.py natal` CLI + Markdown):**

- **Sect** — diurnal/nocturnal from the Sun vs the horizon; sect light; benefic
  and (in-/out-of-sect) malefic of the sect; planetary sect membership;
  orientality (for Mercury's sect).
- **Essential dignities** — domicile, exaltation (+ degree), triplicity (by
  sect), Egyptian term, Chaldean face; detriment and fall; peregrine; the
  +5/+4/+3/+2/+1 dignity score; and the **almuten of a degree** (with the almuten
  of the Ascendant surfaced in the chart). Reference tables verified per §4.
- **Lots** — the seven Hermetic lots (Fortune, Spirit, Eros, Necessity, Courage,
  Victory, Nemesis), each via the uniform day/night-reversing rule.
- **Houses** — Alcabitius added to the house-system map (Swiss Eph `B`) and is
  the medieval default.
- **Profections** — annual profection (one sign/house per completed year from
  the Ascendant, 12-year cycle), the lord of the year, the monthly profected
  sign, and the lord of the year's natal condition (sign/house/dignity). Exposed
  as the `medieval.py profection` subcommand — predictive, so explicit-only.
- **Antiscia / contra-antiscia** — the solstitial and equinoctial reflections of
  each classical planet, plus antiscia contacts within orb.
- **Mutual reception** — pairs of classical planets each occupying a place the
  other rules (by domicile or exaltation by default; minor dignities opt-in).

The computation is **deterministic and emits no prose** — consistent with the
rest of the skill, the medieval CLI prints numbers and dignity states only. The
seven classical planets are the only bodies scored (the modern planets /
asteroids / nodes carried in the natal chart have no essential dignity).

**Not yet built:** triplicity *participating*-ruler scoring nuances aside, the
remaining §3 techniques (triplicity-lord reporting, additional lots beyond the
seven Hermetic, firdaria, solar revolutions, lunar mansions,
planetary hours, fixed stars, temperament, hyleg/alcocoden, almuten figuris);
the entire **interpretation + citation layer (§5)**; the medieval **`.docx`/`.pdf`
renderer branch (§6)**; and **primary directions** (separate, deferred). The
`SKILL.md` "which system?" clarify-step and trigger phrases are also still to come
— so the medieval CLI is currently a direct-invocation tool, not yet surfaced
through the skill's natural-language layer.

## 4. Reference tables (must be verified, never recalled)

The numeric tables are the highest factual-accuracy risk and must be
cross-checked against authoritative sources before use, never reproduced from
memory: term/bound tables (Egyptian, Ptolemaic), face/decan rulers, exaltation
degrees, dignity point-scores, triplicity rulers, firdaria period lengths and
ordering, lunar-mansion boundaries, and the fixed-star catalogue. See §7. Which
*variant* of a table to adopt (e.g. Egyptian vs Ptolemaic terms) is a **convention
choice** that changes the computation — distinct from citation omission (§5.3),
and not yet specced.

## 5. Interpretation and citations

This is the defining feature of the module: **interpretations cite actual
literature** — down to pinpoint loci — with a supporting bibliography as a rare
fallback. This serves working with traditional-astrology experts, who each
favour particular authors and editions.

### 5.1 The verified-corpus rule (citations are never generated)

Interpretation prose is LLM-authored (extending the interpretation system in
[`primary.md`](primary.md) §7), but **citations are looked up from a curated,
verified reference corpus — never generated from model memory.** A citation that
does not resolve to a corpus entry is dropped or flagged, never emitted. This is
deliberate: free-form generated loci are plausible but frequently wrong (wrong
section numbers, conflated authors, passages that don't say what's claimed), and
that failure is unacceptable for a citation-bearing module. Sourcing citations
from verified data makes fabrication **structurally impossible** rather than
merely discouraged.

### 5.2 Granularity — pinpoint loci are the norm

Inline **pinpoint citation** is the default (e.g. *Tetrabiblos* III.10; a Bonatti
*Consideration* §; a Sahl section; an aphorism number). Prefer **edition-stable
loci** (chapter / aphorism / section) over page numbers, which vary by printing.
A **supporting bibliography** (a list of works, no pinpoint) is the rare fallback
for synthesis claims that span sources or where no single clean locus exists.

### 5.3 Pluralism — inclusive by default, per-invocation opt-out

**All verified authors are cited by default** — zero configuration. A reader who
wishes to suppress a source does so **per invocation** (ephemeral; no persisted
exclusion state), excluding **by author, by work, or by edition/translation**.
The default stays zero-config; an omit list is supplied only on the run where a
source is to be suppressed. (Selectable per-tradition citation *sets* remain a
possible future addition; the opt-out model is the simpler first cut.)

**Omission filters citations, not computation.** Excluding an author / work /
edition changes only which verified entries are available to cite; the computed
chart — positions, dignities, sect, lots, profections — is invariant (it does not
depend on who is quoted). A claim another non-excluded source also covers
re-stands, cited to that source; a claim *only* the excluded source covered loses
its citation and is not asserted (§5.1). Choosing a **different author's method**
(e.g. Egyptian vs Ptolemaic terms, a variant lot formula or dignity scheme) is a
separate lever in the convention / reference-table layer (§4), **not** the
omission filter, and is not specced here.

### 5.4 Provenance — snippet plus link

Each verified entry stores a short **verbatim supporting snippet** and a **link
to the source document where one is available** (best-effort: public-domain
originals are linkable; modern translations often are not). The snippet lets a
reader — or an expert reviewer — check the claim against the source directly, and
is the primary defence against *mis-application* (see §5.7).

### 5.5 Corpus entry schema

The corpus lives at `references/medieval/` (extending the `references/*.md`
interpretation grounding [`primary.md`](primary.md) anticipates) and is
**serialized as YAML** (human-curated, multiline snippets, comments). Each entry:

```yaml
id: lilly-ca-fortuna-by-sect          # stable unique slug; what prose references and the resolver validates

keys:                                  # how a chart feature maps to this entry (the lookup index)
  technique: lot                       #   essential-dignity | lot | sect | triplicity | profection |
  subject: lot-of-fortune              #   firdaria | lunar-mansion | fixed-star | aspect | temperament | …
  conditions: { sect: nocturnal }      #   optional qualifiers: sign, house, day/night, dignity state, planet…

claim: >                               # the grounded assertion in the skill's voice (what prose may rely on)
  By night the Lot of Fortune is taken from the Moon to the Sun and
  projected from the Ascendant — the reverse of the diurnal formula.

source:
  author: lilly                        # normalized id  → citation + omission filter
  author_display: William Lilly
  work: christian-astrology            # normalized id  → citation + omission filter
  work_display: Christian Astrology
  edition: regulus-1985                # normalized id  → provenance + omission (omit-by-edition)
  edition_display: "Regulus facsimile (1985) of the 1647 edition"
  kind: pinpoint                       # pinpoint | bibliography
  locus: "Bk II, p. 143"               # edition-stable pinpoint (chapter/aphorism preferred; page as fallback)
  url: "https://…"                     # optional, best-effort link

snippet: >                             # short verbatim quotation — provenance + verifiability
  "…the Part of Fortune is thus in a nocturnal Geniture taken from the
  Moon unto the Sun…"

verified: true                         # ONLY true entries render; drafts stay quarantined
verified_by: "primary text / reviewer" # optional: who/what confirmed it
verified_on: 2026-06-01

notes: >                               # optional internal caveats (not rendered)
  Non-reversal school does not flip Fortune by sect — see <other entry>.
```

Field roles:

- **`id`** — stable handle the prose references and the resolver validates against.
- **`keys`** — the index a chart feature is matched against (`technique` / `subject` / optional `conditions`).
- **`claim`** — the grounded assertion the prose may rely on.
- **`source.author` / `work` / `edition`** — **normalized ids** (lowercase slugs) used by both the citation renderer and the per-invocation omission filter; display names are separate fields.
- **`source.kind`** — `pinpoint` (carries `locus`) vs `bibliography` (no pinpoint).
- **`source.locus` / `url`** — the edition-stable pinpoint and an optional link.
- **`snippet`** — verbatim supporting quotation (short — citation-length — to stay within fair use for in-copyright editions).
- **`verified` / `verified_by` / `verified_on`** — only `verified: true` entries render; unverified drafts stay quarantined.
- **`notes`** — internal caveats, not rendered.

### 5.6 File layout

`references/medieval/<author>.yaml` — **one file per author** (mirrors the
citation/omission unit and lets a curator own one author's entries). At startup
the loader reads all files and builds an in-memory index on `keys`.

### 5.7 Resolution architecture — who does what

Citation handling is split so the *no-fabrication* guarantee is enforced by
deterministic code, not trusted to the model:

1. **Lookup (deterministic / Python).** Load the corpus, index on `keys`, apply
   the per-invocation omission filter (author/work/edition), and — given the
   chart's computed features — return the matching **verified** entries (id,
   claim, citation, snippet, link).
2. **Prose + selection (LLM).** From those candidates, the model chooses what to
   foreground for the reading and writes the interpretation, attaching citations
   **by entry `id`** — never by typing an author/work/locus.
3. **Validate + materialize (deterministic / Python).** At render time, each
   referenced `id` is looked up and the actual citation text + snippet + link are
   emitted **from the corpus**. An `id` that does not resolve to a verified entry
   is dropped or flagged.

Because the model emits only ids and the deterministic layer materializes the
citation from data, **a fabricated citation is structurally impossible** — the
worst case is a reference to a non-existent id, which fails closed. The residual
risk is **mis-application** (citing a real, verified source for a claim it does
not quite support); this is softer and reviewable, and the stored `snippet` is
the mitigation — a reviewer sees the verbatim quote beside the claim and judges
the fit. Having the lookup match chart features to entries (rather than the model
free-associating) constrains mis-application further.

## 6. Integration with the existing skill

- **Interpretation system** — extends [`primary.md`](primary.md) §7: prose stays
  LLM-authored; citations are the new corpus-sourced layer.
- **Chart kind** — a medieval chart payload that the existing renderers serialize
  (a new branch in the kind detection on both the Python and Node sides), with a
  per-kind renderer for the dignities / lots / time-lord output.
- **Reference library** — `references/medieval/` is the concrete instance of the
  `references/*.md` library the spec already anticipates.
- **CLI surface** — a medieval chart entry point plus the per-invocation
  `--omit-author` / `--omit-work` / `--omit-edition` options.

## 7. Building and verifying the corpus

Populating the citation corpus — sourcing authoritative editions, the
draft → verify → maintain workflow, the build toolchain, and collaborative
validation — is a separate effort specified in
[`../research/biblio.md`](../research/biblio.md). The invariant the rest of this
spec relies on: **only `verified: true` entries render; drafts are quarantined and
never appear in output.**

## 8. Open implementation items

- **`keys` vocabulary** — the controlled tag set for `technique` / `subject` /
  `conditions`; best fixed alongside the first techniques implemented.
- **Plumbing** — the corpus loader + `keys` index, the omission filter, and the
  citation resolver/validator/materializer described in §5.7.
- **Corpus build tooling** — validator, snippet-verifier, and coverage report for
  populating the corpus; specified in [`../research/biblio.md`](../research/biblio.md).
- **Cited-only vs hybrid prose** — when a chart feature's only verified entries are
  excluded (or none exist), does the reading stay silent there (strict
  cited-claims-only), or may the model add general *uncited* synthesis? This
  governs how cited and uncited prose coexist, and what an exclusion or a coverage
  gap actually does to a reading. Not yet decided.
- **Primary directions** — deferred (high-effort), tracked as separate work.

## 9. Relationship to other systems

This shares the lots / sect / profections / triplicities substrate with the
planned Hellenistic system and reuses the entire positional pipeline of the
Western tropical core. It is a distinct track today; a future consolidation into
a single continuous European-astrology track (Hellenistic → medieval →
Renaissance) is possible but not planned yet.
