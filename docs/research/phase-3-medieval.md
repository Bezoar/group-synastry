# Phase 3 research — Medieval European astrology

**Status:** scoping rationale + decision log for the medieval / traditional
European track. The settled design is specified in
[`docs/specs/medieval.md`](../specs/medieval.md); the authoritative current-state
spec remains [`docs/specs/primary.md`](../specs/primary.md).
**Date:** 2026-05-24
**Question assessed:** whether there's enough in training-data knowledge plus
deep web verification to add **medieval European astrology** as a Phase 3 system
— answered in the Verdict below (yes).

---

## Verdict

**Feasible, and arguably the best-fit traditional system to add.** The reason is
structural: the hard, accuracy-critical part — precise planet / house / angle
positions — is **already solved** by the Swiss Ephemeris layer. Medieval
astrology is **tropical** (no sidereal conversion) and typically uses
**Alcabitius houses** (Swiss Eph house code `B`, already supported). Almost
everything medieval-specific is **deterministic arithmetic and lookup tables
layered on positions we already compute** — cheap and reliable to implement.

The main caveats are (1) several numeric tables are hallucination-prone and must
be verified against authoritative sources, and (2) primary directions are a
genuine engineering effort.

## Knowledge confidence tiers

### High confidence — concepts and mechanics reproducible from training data

- **Essential dignities**: the five-fold scheme — domicile, exaltation,
  triplicity, term/bound, face/decan — plus detriment/fall, and the **almuten**
  concept (lord of a degree or chart by weighted dignity score).
- **Sect**: diurnal/nocturnal, the sect light, benefic/malefic of the sect, *hayz*.
- **Triplicity rulers** (Dorothean day / night / participating), **planetary
  joys**, the **Chaldean order**, **planetary hours** and the planetary week.
- **Lots / Arabic Parts**: Fortune (ASC + Moon − Sun by day, reversed by night),
  Spirit, and the wider catalogue, including the day/night reversal rule.
- **Time-lord techniques**: annual/monthly **profections**, **firdaria** (Persian
  planetary periods), **solar revolutions** (returns).
- **Reception**, **antiscia / contra-antiscia**, aspects-by-sign with planetary
  **moieties / orbs**, the **28 lunar mansions** (manzil), **temperament**.
- The textual lineage: Ptolemy → Dorotheus / Masha'allah / Abu Maʿshar / Sahl
  (Perso-Arabic) → Bonatti, Ibn Ezra, al-Bīrūnī → the Renaissance tail (Lilly).

### Verify against sources — structure known, exact digits risky

- **Term/bound tables** (Egyptian vs Ptolemaic) — exact degree boundaries and
  rulers per sign. Easy to transpose; must be checked.
- **Face/decan rulers**, **exact exaltation degrees**, and the **dignity
  point-scores** (the +5/+4/+3/+1 weighting).
- **Firdaria** year-counts and sub-period ordering (and node handling).
- **Fixed stars** — longitudes are precession-dependent (need an epoch; Swiss
  Eph's `swe_fixstar` handles this) and the **Behenian 15** with their planetary
  natures.

### Hard — real engineering and convention choices

- **Primary directions** — semi-arc / Placidian, Regiomontanus mundane, zodiacal
  with/without latitude, direct & converse, and the time-key choice (Ptolemy
  1°=1yr, Naibod…). Involved spherical trig with several competing conventions.
  The one piece that is substantial code, not a lookup.
- **Hyleg / alcocoden** (length of life) and **almuten figuris** (lord of the
  geniture) — procedures have variant rules across authors.

## What's already done (computational reuse)

- **Positions, houses, angles** — Swiss Ephemeris, including **Alcabitius** (`B`).
- **Fixed stars** — `swe_fixstar` is available; needs the star list + natures.
- **Everything else** — dignities, lots, sect, triplicities, profections,
  firdaria, lunar mansions, antiscia, planetary hours — is deterministic
  arithmetic on positions we already produce.

## Implementation feasibility by component

| Component | Effort | Notes |
|---|---|---|
| Essential dignities + almuten of a degree | Low–Med | tables + scoring; verify digits |
| Sect, planetary joys, planetary hours/week | Low | deterministic |
| Lots / Arabic Parts (catalogue + day/night reversal) | Low | formulas on positions |
| Profections (annual/monthly) + year-lord | Low | arithmetic |
| Firdaria | Low–Med | period tables; verify order + nodes |
| Solar revolutions (returns) | Med | cast a chart at the return moment (reuse `compute_natal`) |
| Lunar mansions (28) | Low | boundary table |
| Antiscia / contra-antiscia | Low | reflection arithmetic |
| Reception + medieval orbs/moieties | Low–Med | orb table |
| Fixed stars (Behenian + contacts to points) | Med | `swe_fixstar` + star table/natures |
| Temperament | Med | rule synthesis |
| Hyleg / alcocoden (length of life) | Med–High | variant rules |
| Almuten figuris (lord of geniture) | Med | weighted scoring; conventions |
| Primary directions | High | spherical trig; multiple conventions; key choice |
| Horary / elections (if wanted) | Low compute / Med interpretive | mostly an interpretive layer |

## Relationship to the spec's "Hellenistic" Phase 3 item

This overlaps heavily with the deferred **Hellenistic** item in `primary.md` §10.
Lots, sect, profections, and triplicities are the Hellenistic substrate; medieval
European **extends** it — firdaria, Alcabitius houses, an expanded lot catalogue,
lunar mansions, richer dignity scoring, primary directions, and horary. So this
is best modeled **not as a fourth disjoint system but as an enriched superset**
that reuses the same infrastructure. Worth deciding whether "medieval" subsumes
or sits beside "Hellenistic" in the roadmap.

## Terminology / era boundary

"Medieval European" has fuzzy edges. The Latin West (Bonatti, ~12th–15th c.)
translated Perso-Arabic sources (8th–10th c.), and the tradition shades into
Renaissance / early-modern (Lilly, 17th c.). The modern "traditional astrology"
revival treats these fairly continuously. The chosen **anchor author/era changes
defaults** — dignity scoring, house system, which lots are standard — so it needs
to be pinned before building.

## Sourcing / verification plan

For the table-level facts, web search closes the gap, but anchor on
**authoritative** references and cross-check, rather than scraping a random
astrology blog (numeric tables are exactly where bad sources propagate errors):

- Ptolemy, *Tetrabiblos* (the foundation, esp. terms/triplicities).
- William Lilly, *Christian Astrology* (dignity table, orbs, horary).
- Benjamin Dykes' translations of Bonatti, Sahl, Abu Maʿshar (modern scholarly).
- Established standardized dignity / term / face tables, cross-checked across ≥2
  reputable sources before committing a number.
- Swiss Ephemeris docs for `swe_fixstar` and the bundled fixed-star catalogue.

## Citation strategy (interpretation module)

A defining requirement for the medieval module: **interpretations should cite
actual literature wherever possible** — down to pinpoint loci — with a supporting
**bibliography** as a rare fallback. This is driven by working with
medieval-astrology experts, who each favour particular authors and editions.

### The risk this must design around

Citations are the **highest hallucination-risk surface** in the feature. An LLM
generating loci from memory ("Bonatti, *Liber Astronomiae*, Tr. 5 §43") produces
plausible, edition-shaped, and frequently **wrong** references — wrong section
numbers, conflated authors, passages that don't say what's claimed. Experts catch
these instantly, and a few fabricated cites would poison trust in the whole
module. The architecture must make fabrication **structurally impossible**, not
merely discouraged.

### Load-bearing decision: cite from a verified corpus, never from model memory

Split the two things the §7 interpretation system does:

- **Prose** — still LLM-authored.
- **Citations** — *looked up* from a curated, verified reference corpus, **not
  generated**. A citation that does not resolve to a corpus entry is dropped or
  flagged — never emitted. This converts "did the model invent this?" into "is it
  in the verified data?", a checkable property.

Concretely: a `references/medieval/` corpus (extends the `references/*.md`
interpretation grounding the spec already anticipates — §7.1, §11), keyed by
technique / placement / dignity, each entry carrying the claim, author, work,
edition/translation, a **canonical locus**, a verification flag, and — for
provenance — a **verbatim supporting snippet** plus a **link to the source
document where one exists**. Entries are tagged by author/work so they can be
filtered (see design point 3).

### Design points

1. **Canonical loci over page numbers.** Cite *Tetrabiblos* III.10, a Bonatti
   *Consideration* §, a Sahl section, an aphorism number — these are
   edition-stable. Page numbers vary by printing and are the easiest thing to get
   wrong. Record the edition (e.g. "Dykes trans.") for provenance regardless.
2. **Two modes.** Inline pinpoint citation is the default ("wherever possible"); a
   **supporting bibliography** (works list, no pinpoint) is the fallback for
   synthesis claims spanning sources, or where no single clean locus exists. The
   existing interpretation pipeline (markdown sections + sidecar) renders both —
   inline refs/footnotes plus a "Sources" section.
3. **Inclusive by default, opt-out omission.** All verified authors are cited by
   default — zero configuration. An individual can **omit specific works or
   authors** when needed (e.g. an expert who rejects a given source) via an
   exclusion list, rather than assembling a citation set up front. This keeps the
   common case zero-config and sidesteps the UX trap of forcing users to curate a
   set before they can get a reading. (Corpus entries are tagged by author/work,
   so the omission filter just drops matching entries before composing
   citations.) Fuller *selectable* per-tradition sets remain possible later, but
   the opt-out model is the safer first cut.

### Verification workflow

The corpus is populated by cross-checking against the **actual texts** —
authoritative editions and the experts, far more than model recall. The model is
useful for *drafting* candidate entries quickly; dangerous if trusted to *assert*
a locus unverified. So: model drafts → verified against the primary source
(expert or text) → only then enters the corpus with a `verified` flag.
Unverified drafts stay quarantined and never render. For the strongest
provenance, an entry can store a verbatim supporting snippet so any reader can
check the claim directly.

### Decisions (resolved 2026-05-24)

- **Granularity** — **pinpoint loci are the norm; bibliography is the exception.**
- **Pluralism** — **all authors included by default; an individual may omit
  specific sources (opt-out)**, rather than assembling a set up front. The
  omission is **specified per invocation** (ephemeral — no persisted exclusion
  state) and accepts exclusions **by author, by work, or by edition/translation**.
  The default stays zero-config; an omit list is passed only when suppressing a
  source for that particular run.
- **Provenance depth** — **store a verbatim supporting snippet per verified
  entry, plus a link to the original document where available.** Links are
  best-effort (public-domain originals — Ptolemy, Lilly, Bonatti — are linkable;
  modern translations often are not); keep snippets short (citation-length) to
  stay within fair use for in-copyright editions.

## Decisions and remaining work

Tracked on the Phase 3 ticket (Medieval/Traditional European track) and a
separate primary-directions ticket. The settled design is specified in
[`docs/specs/medieval.md`](../specs/medieval.md).

Resolved 2026-05-24:

1. **Era anchor** — ✅ the broad **"traditional" band**: Latin medieval (Bonatti),
   the Perso-Arabic sources, and the Renaissance tail (incl. Lilly), treated
   continuously.
2. **Depth** — ✅ **everything**: natal + synastry + returns, plus the
   predictive/time-lord layer (firdaria, profections, solar revolutions).
   Primary directions split out (see item 4).
3. **House default** — ✅ **Alcabitius** (Swiss Eph `B`); other house systems may
   be added later.
4. **Primary directions** — ✅ **deferred to a separate ticket** — the one
   high-effort piece, scheduled independently of the medieval first cut.
5. **Roadmap placement** — ✅ a **separate track from Hellenistic for now**; the
   two may later merge into a single continuous European-astrology track (they
   share the lots/sect/profections/triplicities substrate), but not yet.
6. **Plumbing** — ✅ confirmed: a `references/medieval/` corpus (extends the
   anticipated `references/*.md` interpretation library) + eval reference data.
7. **Citation strategy** — ✅ the three steering decisions resolved (see
   "Citation strategy → Decisions").
8. **Citation omission surface** — ✅ **per invocation** (ephemeral, no persisted
   state), accepting exclusions by author, work, or edition/translation.
9. **Corpus entry schema + resolution architecture** — ✅ specified in
   [`docs/specs/medieval.md`](../specs/medieval.md) §5: a YAML corpus at
   `references/medieval/<author>.yaml`; citation resolution is **Python-side**
   (lookup + validate/materialize), with the model writing prose and citing
   entries **by id** — never authoring the citation text.

The full design is now in `docs/specs/medieval.md`; this note is the scoping
rationale and decision log behind it.
