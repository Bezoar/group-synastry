# PR #35 — research sources for reference-table verification

**Scope:** the sources consulted while building group-synastry-private
PR #35 (the Medieval/Traditional track + Hellenistic foundation on
`feat/phase3`). Per the verify-don't-recall discipline
(`docs/specs/medieval.md` §4), every numeric reference table was
cross-checked against external sources rather than reproduced from
memory. This file records **every** source consulted — those that
yielded data, those used as independent cross-checks, and those that
were blocked / image-only / dead (kept for transparency and to save a
future re-verification pass from re-trying them).

**Date:** 2026-05-25
**Location note:** `docs/research/` is NOT `export-ignore`d (see `.gitattributes`;
only `docs/generated/` and `docs/instructions/` are), so this note publishes to the
public mirror. That is safe: it cites only public astrology references — no private
birth data.

> **Status of these sources.** These are *accessible web cross-checks used during
> development*, **not** citation-grade primary editions. They are good enough to
> pin deterministic computation tables (corroborated by ≥2 independent sources +
> internal-consistency + the integrity guards in `test_medieval.py`). They are
> **not** sufficient for the citation corpus proper (`docs/specs/medieval.md` §5,
> `docs/research/biblio.md`), which requires verification against authoritative
> editions (Ptolemy, Lilly, Dykes' translations, etc.).

Legend: ✅ yielded the data used · ➕ independent cross-check · 📝 reference/context
· ✗ consulted but unusable (blocked / image-only / dead).

---

## Essential dignities

### Domicile (rulerships)
The traditional seven-planet rulership scheme is universal and unambiguous.
- ➕ Wikipedia, *Essential dignity* — <https://en.wikipedia.org/wiki/Essential_dignity> — confirmed the domicile/detriment table is present for all 12 signs.

### Exaltation (sign + degree)
- ✅ Wikipedia, *Exaltation (astrology)* — <https://en.wikipedia.org/wiki/Exaltation_(astrology)> — Sun 19° Aries, Moon 3° Taurus, Mercury 15° Virgo, Venus 27° Pisces, Mars 28° Capricorn, Jupiter 15° Cancer, Saturn 21° Libra (also lists Nodes 3° Gemini / 3° Sagittarius, noting little Western use).
- ➕ flatlib `tables.py` (below) — exaltation degrees agreed exactly.
- ✗ astro.com Astrowiki, *Exaltation* — <https://www.astro.com/astrowiki/en/Exaltation> — Cloudflare bot-check; no content returned.

### Triplicity rulers (Dorothean)
- ✅ Wikipedia, *Triplicity* — <https://en.wikipedia.org/wiki/Triplicity> — day / night / participating by element: Fire = Sun / Jupiter / Saturn; Earth = Venus / Moon / Mars; Air = Saturn / Mercury / Jupiter; Water = Venus / Mars / Moon (+ the Ptolemaic water-triplicity modification to Mars). Used as primary because it is internally consistent by element.
  - *Note:* flatlib's per-sign triplicity transcription came back garbled/non-element-consistent in the fetch, so Wikipedia's element table was used instead.

### Egyptian terms / bounds
The single highest-risk table; verified against multiple sources.
- ✅ flatlib `dignities/tables.py` (raw) — <https://raw.githubusercontent.com/flatangle/flatlib/master/flatlib/dignities/tables.py> — the full 12-sign Egyptian-bounds table (the working source). flatlib is a respected traditional-astrology Python library (João Ventura).
- ➕ Kira Ryberg, *The Power of the Bounds (Egyptian Terms)* — <https://www.kiraryberg.com/blog/the-bounds> — independently confirmed the **Aquarius** row (Mercury 0–7, Venus 7–13, Jupiter 13–20, Mars 20–25, Saturn 25–30).
- ➕ Web search summary — corroborated the **Aries** distribution (Jupiter 6°, Venus 6°, Mercury 8°, Mars 5°, Saturn 5°) and the benefic-7° / malefic-5° / Mercury-6° pattern.
- 📝 Skyscript, *Essential Dignities* (intro) — <http://www.skyscript.co.uk/dignities.html> — flagged that its consolidated table is **Ptolemaic** (Aries Venus 6–14), which surfaced the Egyptian-vs-Ptolemaic distinction; used to *avoid conflating* the two (the module uses the Egyptian set).
- ✗ astro.com Astrowiki, *Terms* — <https://www.astro.com/astrowiki/en/Terms> — Cloudflare bot-check.
- ✗ Altair Astrology, *More on the Terms or Bounds* — <https://altairastrology.wordpress.com/2009/03/01/more-on-the-terms-or-bounds/> — tables are PNG images (Egyptian / Ptolemaic / Chaldean), not text.
- ✗ Seven Stars Astrology, *The Bounds — Tables and Origins* — <https://sevenstarsastrology.com/bounds-tables-origin/> — references the table but does not transcribe it.
- ✗ The Zodiacus, *Of the Disposition of Terms: the 3 systems* — <https://thezodiacus.com/2021/06/27/of-the-disposition-of-terms-the-3-systems-according-to-egyptian-ptolemy/> — domain expired / squatted (returned casino spam).
- ✗ Astro Gold help, *Terms* — <https://www.astrogold.io/AG-iOS-Help/terms.html> — concept only, no table.
- ✗ Skyscript dignities table page — <http://www.skyscript.co.uk/dig2.html> — table is an image.

### Faces / decans (Chaldean order)
- ✅ flatlib `dignities/tables.py` (raw) — <https://raw.githubusercontent.com/flatangle/flatlib/master/flatlib/dignities/tables.py> — the full 12-sign face table; verified internally consistent with the continuous Chaldean order (Saturn→Jupiter→Mars→Sun→Venus→Mercury→Moon, with the known "double Mars" at the Pisces→Aries wrap).
- ➕ Skyscript, *Essential Dignities* — <http://www.skyscript.co.uk/dignities.html> — confirmed Aries 1st face = Mars, 2nd = Sun.
- ✗ Wikipedia, *Decan* — <https://en.wikipedia.org/wiki/Decan> — does not contain the Chaldean planetary-ruler table.

### Dignity point-scores
- ✅ Wikipedia, *Essential dignity* — <https://en.wikipedia.org/wiki/Essential_dignity> — verbatim: "+5 domicile, +4 exaltation, +3 triplicity, +2 terms, +1 decan."

### Sect, almuten, antiscia, mutual reception
Deterministic mechanics/arithmetic layered on the verified tables above — no new
numeric table required. Sect = Sun above/below the horizon (+ the in/out-of-sect
benefic/malefic assignments, standard); almuten = the +5/+4/+3/+2/+1 weighting
applied over a degree; antiscia = reflection across the solstitial axis
(`180 − λ`) and contra-antiscia across the equinoctial axis (`−λ`); mutual
reception = pairs of planets each in a sign the other rules (domicile/exaltation).

---

## Lots — the seven Hermetic lots (Paulus Alexandrinus set)

- ✅ Web search result — the canonical lot↔planet correspondence: Fortune (Moon),
  Spirit (Sun), Eros (Venus), Necessity (Mercury), Courage (Mars), Victory
  (Jupiter), Nemesis (Saturn).
- ✅ Two Wander, *What are the Hermetic Lots (Arabic Parts)?* — <https://www.twowander.com/blog/what-are-hermetic-lots-arabic-parts> — explicit day/night formulas for Eros (Asc + Venus − Spirit), Necessity (Asc + Fortune − Mercury), Courage (Asc + Fortune − Mars), Victory (Asc + Jupiter − Spirit).
  - *Correction applied:* this page printed Nemesis as `Asc + Fortune − Spirit`, which contradicts the Nemesis↔Saturn correspondence and the Fortune-derived family pattern — treated as a typo and corrected to **`Asc + Fortune − Saturn`**.
- ➕ Astrology API, *Arabic Parts* — <https://astrology-api.io/p/arabic-parts> — confirmed Eros & Victory are Spirit-derived and Nemesis is *Fortuna*-derived ("Retribution from Fortuna"); this resolved the Nemesis typo above. Cites Paulus Alexandrinus (378 CE) as the origin.
- 📝 Paulus Alexandrinus, *Introductory Matters* — the historical source of the seven Hermetic lots (named by the calculator/API sources; a citation-grade edition is the corpus's job, not verified here).
- ✗ Seven Stars Astrology, *Twelve Easy Lessons #7 — The Lots* — <https://sevenstarsastrology.com/twelve-easy-lessons-for-beginners-7-the-lots/> — uses a *different* lot tradition (its "Necessity" is Spirit→Fortune, reversed from the Hermetic set); deliberately **not** used, to avoid mixing conventions.
- ✗ Augurine, *Arabic Parts Calculator* — <https://www.augurine.com/tools/arabic-parts-calculator> — calculator UI; formulas not in the page text.
- 📝 Other search hits, not individually fetched: Augurine *Lot of Eros* (<https://www.augurine.com/tools/lot-of-eros>), Kira Ryberg *The Hermetic Lots* lecture (<https://www.kiraryberg.com/lectures/p/the-hermetic-lots-an-exploration-into-their-mysteries>), YourTango *7 Hermetic Lots* (<https://www.yourtango.com/zodiac/7-hermetic-lots-astrology>), Skyscript forum thread (<https://www.skyscript.co.uk/forums/viewtopic.php?t=5523>), Astrology X-Files *Arabic Parts* (<https://www.astrology-x-files.com/x-files/arabic-parts.html>), Augurine *transmission history of the Arabic Lots* (<https://www.augurine.com/blog/insights/transmission-history-arabic-lots>).

---

## Profections (annual / monthly)

These are mechanics, not a numeric table, so a search-summary corroboration was
sufficient (cross-checked against the convention, not a digit table).
- ✅ Web search summary ("annual profections Hellenistic age 0 …") — confirmed: age 0 = the 1st-house / Ascendant-sign year; advance one whole sign/house per completed year in zodiacal order; 12-year cycle; the lord of the year is the ruler of the profected sign; lineage Dorotheus of Sidon / Vettius Valens.
- ✗ Wikipedia, *Annual profection* — <https://en.wikipedia.org/wiki/Annual_profection> — 404 (no such page); recorded so a re-verification pass doesn't re-try it.
- 📝 Search hits, not individually fetched: Thalira (<https://thalira.com/blogs/quantum-codex/annual-profections-astrology>), Bonnie Sorsby (<https://bonniesorsby.com/annual-profections-astrology/>), Astrology with Heather (<https://www.astrologywithheather.com/blog/annual-profections>), Selfgazer (<https://www.selfgazer.com/blog/profection-year-chart-astrology>), Two Wander (<https://www.twowander.com/blog/annual-profections-guide>), Astrostyle (<https://astrostyle.com/astrology/annual-profection-hellenistic-astrology/>), Augurine *Profection Year* (<https://www.augurine.com/tools/profection-year>), Kerykeion *the annual profection lord* (<https://kerykeion.net/content/learn-astrology/traditional-profection-lord>), Tarostarot (<https://tarostarot.com/profection-year-calculator>), Astro-Seek (<https://horoscopes.astro-seek.com/annual-profections-astrology-calculator>).

---

## Positions & houses (not web-sourced)

- **Swiss Ephemeris (pyswisseph)** is the authority for planet/angle positions and
  house cusps, including **Alcabitius** (house code `B`, added in this PR). No web
  source needed — positions are computed, not looked up.

---

## How the tables were actually validated

Beyond the cross-source agreement above, the load-bearing checks were:
1. **Internal consistency** — every Egyptian-term row sums to 30°; the Chaldean
   face cycle is continuous; the triplicity rulers are element-consistent.
2. **Cross-source agreement** — ≥2 independent sources per risky table (e.g.
   Egyptian terms: flatlib + Kira Ryberg + search; exaltations: Wikipedia +
   flatlib).
3. **Integrity guards in `test_medieval.py`** — term rows sum to 30°, each planet
   rules the expected count of domiciles, the lot↔planet mapping is pinned, etc.

## Authoritative anchors for any future re-verification

Per `docs/specs/medieval.md` §4 and `docs/research/biblio.md`, the citation-grade
anchors to cross-check against (not used as live sources in this dev pass) are:
Ptolemy's *Tetrabiblos*; William Lilly's *Christian Astrology* (the consolidated
dignity table, p. 104 — note: **Ptolemaic** terms); Benjamin Dykes' translations
of Bonatti, Sahl, and Abu Maʿshar; and ≥2 reputable cross-checks before any
number is committed.
