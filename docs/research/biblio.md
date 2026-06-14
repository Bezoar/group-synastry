# Citation corpus — building and validating the bibliography

**Status:** research / plan for a sub-project of the medieval / traditional
European track. Companion to [`../specs/medieval.md`](../specs/medieval.md),
which specifies the citation *system* (the corpus entry schema, §5.5; the runtime
resolution architecture, §5.7). This note covers how the corpus is **populated
and verified** — a distinct effort from computing charts, with its own workflow,
tooling, and correctness discipline.

Scope boundary: this sub-project builds the **citation corpus** only. Excluding a
source filters which *citations* appear, never the computed chart (`medieval.md`
§5.3); and *choosing* a computational convention — a term-table variant, a lot
formula — is separate again (`medieval.md` §4). Neither is part of this effort.
**Date:** 2026-05-24

---

## Guiding principle: automate verification, assist drafting, never automate trust

This is the build-time mirror of the runtime guarantee (citations come from a
verified corpus, never model memory). Three distinct activities:

- **Drafting** — a script (or an LLM) may *propose* candidate entries (claim,
  proposed snippet, proposed locus). Everything it produces is `verified: false`:
  quarantined, never rendered.
- **Verifying** — *deterministic*: the `snippet` must be an **exact substring** of
  the cited source, and the locus must resolve. This is what makes
  `verified: true` a *checkable property* rather than a judgment call — and it
  kills the dominant failure mode (a fabricated or misquoted snippet cannot pass).
- **Trust** — does the snippet actually *support* the claim, and is the
  attribution right? This is the human / expert step. A script can only flag what
  it cannot confirm; it never blesses an entry.

So a "scan a document and emit citations" tool, if built, only ever produces
**drafts**. Nothing it writes is trusted until the deterministic check passes and
a human confirms the fit.

## Workflow

1. **Acquire sources** — machine-readable texts where legitimate: public-domain
   originals (Lilly 1647, out-of-copyright translations, Bonatti Latin); for
   in-copyright modern translations, the maintainer/expert works from their own
   owned copies.
2. **Draft entries** — scaffold the YAML (`id` / `keys` / `claim` / `source` /
   `snippet`), `verified: false`. Experts may *supply* candidates (claim + locus)
   directly — often cleaner than machine extraction.
3. **Verify** — run the snippet verifier (exact substring against the source); a
   human confirms claim-fit and locus; on pass, flip to `verified: true` with
   `verified_by` / `verified_on`.
4. **Maintain** — lint, (re)index, and report coverage gaps to drive curation.

## Toolchain

- **Schema validator / linter** — valid YAML, required fields, unique `id`s,
  normalized `author` / `work` / `edition` ids consistent across files.
- **Snippet verifier** — the deterministic substring check against source text;
  the core trust mechanism.
- **Coverage / gap report** — which `keys` (techniques, placements) have citations
  and which are holes; guides what to source next.
- **Drafting helper** — scaffolds a new entry; may LLM-propose candidates, always
  marked draft.
- **Resolver** — the runtime resolver (`medieval.md` §5.7) doubles as a build-time
  "does this id exist / is it verified?" check.

## Collaborative validation

Because every entry is **independently checkable** — snippet-in-source + locus +
claim-fit, with the verbatim snippet stored as evidence — validation distributes
cleanly. A contributor can take one author or one technique, run the verifier,
confirm the claim-fit, and flip the flag. The deterministic check is the gate and
the stored snippet is the evidence anyone can re-check, so we can enlist others to
help validate **without trusting anyone's memory** (ours or theirs). Getting this
tooling right is what makes outside help safe to accept.

## Sourcing (authoritative editions)

Populate the corpus (and the computational reference tables in `medieval.md` §4)
by cross-checking against **authoritative** editions, not casual web sources:
Ptolemy's *Tetrabiblos*; Lilly's *Christian Astrology*; modern scholarly
translations of Bonatti, Sahl, and Abu Maʿshar; standardized dignity / term /
face tables cross-checked across ≥2 reputable sources before a number is
committed; and the Swiss Ephemeris fixed-star catalogue.

## Constraints (honest)

- **Source acquisition is the bottleneck**, not the scripting. Old texts are OCR'd
  with archaic orthography (long-ſ, ligatures); in-copyright translations can't be
  bulk-scanned or redistributed. We store the short `snippet` (citation-length,
  fair use), never whole works — but the verifier still needs the source available
  *somewhere*: in-repo for public-domain texts, a local path the maintainer
  supplies for in-copyright ones.
- **Orthography** — the substring check only matches if the stored source matches
  the snippet's spelling, so a normalization policy (modernized vs facsimile) must
  be chosen up front.
- **The LLM is a drafter, never the verifier** — at build time exactly as at
  runtime.

## Open items / next steps

- A ticket for the **corpus-build toolchain** (validator + snippet-verifier +
  coverage report).
- **Source-text storage** decision: in-repo for public-domain vs a local path for
  in-copyright, and where each lives.
- **Orthography normalization** policy (modernized vs facsimile).
- **Serialization** — YAML is the chosen format; it adds a `pyyaml` dependency
  (the skill currently pins only `pyswisseph`), to confirm at build time.
- The **`keys` vocabulary** (shared with `medieval.md` §8).
- **Coverage-gap semantics** — depends on the cited-only-vs-hybrid question
  (`medieval.md` §8): if readings may add general *uncited* synthesis, a gap in
  the corpus is a missing citation; if readings are strictly cited-only, a gap is
  a real hole the coverage report must drive us to fill. Settle alongside §8.
