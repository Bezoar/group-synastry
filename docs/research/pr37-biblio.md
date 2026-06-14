# PR #37 — research sources for Vedic (sidereal) reference data

**Scope:** the sources behind the reference data introduced in
group-synastry-private PR #37 (the **Vedic / sidereal** foundation,
`lib/vedic.py`): the 27 nakshatra names + order, the Vimshottari dasha
lord cycle, and the ayanamsha set. Per the verify-don't-recall discipline
(`docs/specs/medieval.md` §4), the data tables are corroborated against
external sources rather than reproduced from memory.

This file is a **post-hoc reconstruction.** The code shipped citing
*Wikipedia "Nakshatra"* + the Swiss Ephemeris in its module docstring; the
sources below were (re-)consulted to document and cross-check that, and to
record the authoritative anchors the deferred dasha/divisional work will need.

**Date:** 2026-05-25
**Location note:** unlike `docs/generated/`, **`docs/research/` is NOT
`export-ignore`d** (see `.gitattributes`), so this note publishes to the public
mirror — as does `pr35-biblio.md` beside it. That is safe here: it cites only
public astrology references and the public test subject (Alex); **no private
birth data.** (`pr35-biblio.md`'s own "Location note" mislabels itself as
private — it is not; same directory.)

> **Status of these sources.** Wikipedia + encyclopedic/calculator pages are
> *accessible cross-checks* — good enough to pin deterministic, standardized
> reference data (the nakshatra list and the Vimshottari lord cycle are
> well-established and unambiguous), backed by internal-consistency + the
> integrity guards in `test_vedic.py`. The **ayanamsha values are not
> web-looked-up at all** — they come from the Swiss Ephemeris library itself.
> None of this is a citation-grade classical edition; the authoritative anchors
> (BPHS, Sūrya Siddhānta) are listed at the end for the deferred dasha-timeline /
> Navamsa work that will require them.

Legend: ✅ yielded the data used · ➕ independent cross-check · 📝 reference/context · ✗ consulted but unusable.

---

## Nakshatras — the 27 lunar mansions

Names + order + the 13°20′ span / 3°20′ pada division (`NAKSHATRAS`,
`NAKSHATRA_SPAN`, `PADA_SPAN` in `lib/vedic.py`).

- ✅ Wikipedia, *Nakshatra* — <https://en.wikipedia.org/wiki/Nakshatra> — the 27 in canonical order from 0° sidereal Aries (Aśvinī → Revatī); "Each of the 27 Nakshatras cover 13° 20′ of the ecliptic" and "Each Nakshatra is … divided into quarters or *padas* of 3° 20′."
  - *Romanization note:* the code uses plain-ASCII transliterations (Ashwini, Mrigashira, Ardra, Pushya, Ashlesha, Jyeshtha, Shravana, Dhanishtha, Shatabhisha, Revati, …); Wikipedia uses IAST diacritics (Aśvinī, Mṛgaśīrṣā, Ārdrā, …). Same names, different transliteration scheme — **not** a discrepancy.

## Vimshottari dasha — lord cycle (shipped) and periods (deferred)

PR #37 ships only the **lord assignment** (`VIMSHOTTARI_CYCLE`), used to label
each nakshatra's ruling planet and the janma (Moon) nakshatra's lord. The
**dasha timeline** — which additionally needs the period *years* and a
balance-at-birth calc — is deferred.

- ✅ Wikipedia, *Nakshatra* — <https://en.wikipedia.org/wiki/Nakshatra> — the repeating lord sequence across the 27: **Ketu → Venus → Sun → Moon → Mars → Rahu → Jupiter → Saturn → Mercury**, repeated three times (9 × 3 = 27). Per-nakshatra spot-checks: Aśvinī = Ketu, Ārdrā = Rahu, Puṣya = Saturn, Revatī = Mercury — all match `lib/vedic.py`.
- 📝 *Period years* (for the **deferred** dasha engine — not yet in code): Ketu 7, Venus 20, Sun 6, Moon 10, Mars 7, Rahu 18, Jupiter 16, Saturn 19, Mercury 17 = **120 years**, prescribed by Sage Parāśara in the *Bṛhat Parāśara Horā Śāstra* (BPHS).
  - ➕ astrosutras.in, *Vimshottari Dasha System in BPHS* — <https://astrosutras.in/index.php/2025/03/04/vimshottari-dasha-system-in-brihat-parashara-hora-shastra-bphs/> — periods + explicit BPHS attribution.
  - ➕ Prokerala, *Vimshottari Dasha* — <https://www.prokerala.com/astrology/vimshottari-dasha.php> — the same 120-year split, independently.

## Ayanamsha & sidereal conversion — Swiss Ephemeris (not web-sourced)

The five supported ayanamshas (`AYANAMSAS` in `lib/vedic.py`) and the
`sidereal = tropical − ayanamsha` definition (`to_sidereal`). **These are
library-computed values, not looked-up numbers.**

- ✅ Swiss Ephemeris, *Programmer's documentation* — <https://www.astro.com/swisseph/swephprg.htm> — §12 "Sidereal mode": `swe_set_sid_mode()`, `swe_get_ayanamsa_ut()`; the constants `SE_SIDM_FAGAN_BRADLEY`, `SE_SIDM_LAHIRI` (a.k.a. **Chitrapaksha**), `SE_SIDM_RAMAN`, `SE_SIDM_KRISHNAMURTI`, `SE_SIDM_TRUE_CITRA` — the exact five the code maps — and the stated formula **"sidereal = tropical minus ayanamsha."**
  - Cross-checked in code: `test_vedic.test_to_sidereal_matches_swisseph_native_sidereal_within_tolerance` asserts `tropical − get_ayanamsa_ut()` agrees with swisseph's native `FLG_SIDEREAL` calc to **< 0.02°** (the test tolerance; observed agreement is finer).
- 📝 pyswisseph — the Python binding exposing `swe.SIDM_*`, `swe.set_sid_mode`, `swe.get_ayanamsa_ut`; same upstream data.

## Grahas, rasi houses, arithmetic (standard — no table)

- 📝 The nine grahas (Sun…Saturn + Rāhu/Ketu = the lunar nodes / their opposite point), the whole-sign **rasi** house count from the sidereal Lagna, and the span arithmetic (`360/27`, pada `= span/4`) are universal / derivable — no numeric lookup. Rasi houses reuse the shared `formatting.whole_sign_house` helper, the same whole-sign scheme verified for the Hellenistic layer in PR #35.

---

## How the data was actually validated

1. **Internal consistency** — the Vimshottari cycle is 9 lords and 27 = 9 × 3, so it tiles the nakshatras exactly; `NAKSHATRA_SPAN = 360/27`. Pinned by `test_vedic.test_nakshatra_table_integrity` (27 unique names, 9-lord cycle, span check) and `test_vimshottari_lord_cycle_repeats_thrice_across_27`.
2. **Cross-source agreement** — nakshatra list + lord cycle from Wikipedia; period-years + BPHS lineage independently from astrosutras + Prokerala.
3. **Library cross-check** — the `tropical − ayanamsha` identity checked against swisseph's native sidereal mode (< 0.02°).
4. **Hand-verification (public subject Alex)** — Moon = Ārdrā pada 3 (lord Rahu), Sun sidereal early Gemini, Rāhu/Ketu exactly opposite, Lagna sidereal Cancer — all consistent with the verified tables.

## Authoritative anchors for future re-verification

Most relevant to the **deferred** pieces (Vimshottari dasha *timeline*,
Navamsa / D9), which will need citation-grade sources rather than the
development cross-checks above:

- **Bṛhat Parāśara Horā Śāstra (BPHS)** — the classical source of the nakshatra scheme and the Vimshottari dasha (periods, lordships, balance-of-dasha at birth).
- **Sūrya Siddhānta** — classical basis of the sidereal zodiac / ayanamsha concept.
- **Swiss Ephemeris general documentation** — <https://www.astro.com/ftp/swisseph/doc/swisseph.htm> — the full ayanamsha catalogue and the precise epoch/definition of each mode (Lahiri/Chitrapaksha, Fagan-Bradley, Krishnamurti, Raman, True Citra), for when an ayanamsha *choice* needs justifying.
