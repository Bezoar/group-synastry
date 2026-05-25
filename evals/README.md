# `group-synastry` Eval Suite

Professional-grade evaluation suite for the `group-synastry` skill. Three files, two workflows.

## Files

| File | Purpose | Used by |
|---|---|---|
| `trigger-evals.json` | 52 queries (32 should trigger, 20 should not) covering core asks, ambiguous edges, astronomy traps, skeptical phrasing, and unrelated topics that share vocabulary | `skill-creator/scripts/run_loop.py` for description optimization |
| `behavioral-evals.json` | 18 end-to-end test cases with discriminating assertions tied to specific reference values | `skill-creator` executor + grader workflow |
| `reference-charts.json` | Validated planetary positions, aspects, and chart features for Alex and Jordan's birth charts plus their synastry/composite/Davison. Used as the ground truth for behavioral assertions. | Read by graders (and by humans) when verifying that computed positions are correct |

## Design Philosophy

### What makes a good assertion?

A *discriminating* assertion passes when the skill genuinely succeeds and fails when it doesn't. Bad assertions create false confidence — they pass for plausible-looking-but-wrong outputs.

**Examples from this suite:**

❌ Weak: *"Output includes the Sun's position"*
✓ Discriminating: *"Output reports Sun at 10° Taurus 53' ± 1 arcminute (reference: 10°53')"*

❌ Weak: *"The skill stored the timezone correctly"*
✓ Discriminating: *"When the stored tz is applied to '1988-06-15 08:20' local time, the resulting UTC offset is -05:00"*

❌ Weak: *"The skill produced a chart"*
✓ Discriminating: *"Output includes Chiron AND Eris AND Lilith AND Ceres. Missing any of the four is a fail (per spec D6)"*

### Why three files instead of one?

Separation lets each piece evolve independently. Reference values are versioned facts about the test subjects (Alex and Jordan) — they shouldn't change unless the underlying ephemeris improves. Behavioral evals encode what the skill should do — they evolve with the spec. Trigger evals encode what queries should reach the skill — they evolve with usage patterns.

### Why both abbreviation and IANA tests?

The evals specifically test that the skill stores the IANA name (`America/Chicago`) but resolves it to the historically correct offset (UTC−5) for the birth date. This catches three failure modes:
1. Storing the abbreviation `CDT` (no DST history; breaks for other dates)
2. Storing the wrong IANA name (e.g., `America/Chicago` for Ohio)
3. Storing IANA correctly but applying it wrong (e.g., always returning EST)

A skill could pass any single test by accident. Passing all three requires correct IANA + DST handling.

---

## Running the Trigger Evals (Claude Code only)

```bash
# from inside the skill-creator directory
python -m scripts.run_loop \
  --eval-set /path/to/trigger-evals.json \
  --skill-path /path/to/group-synastry-private/plugins/group-synastry/skills/group-synastry \
  --model claude-opus-4-7 \
  --max-iterations 5 \
  --runs-per-query 3 \
  --verbose
```

This will:
1. Split into 60% train / 40% test (stratified by `should_trigger`)
2. Run each train query 3 times against the current SKILL.md description
3. Ask Claude to propose an improved description based on what failed
4. Re-test on both train and test
5. Repeat up to 5 iterations
6. Output `best_description` chosen by *test* score (not train) to avoid overfitting
7. Open an HTML report you can refresh during the run

Take the winning `best_description` and paste it into `SKILL.md`'s YAML frontmatter.

**This does not run on claude.ai** — it requires the `claude -p` CLI.

---

## Running the Behavioral Evals

### In Claude Code (recommended)

The skill-creator's executor + grader subagents do the work in parallel:

```bash
# Each eval runs the prompt with the skill loaded; grader checks expectations
python -m scripts.run_eval \
  --evals /path/to/behavioral-evals.json \
  --skill-path /path/to/group-synastry-private/plugins/group-synastry/skills/group-synastry \
  --runs-per-eval 1 \
  --verbose
```

Then generate the HTML reviewer:

```bash
python -m scripts.generate_review \
  --grading-dir <results-dir> \
  --output report.html
```

Open `report.html`. For each eval you'll see the prompt, the transcript, and per-expectation pass/fail with the grader's evidence.

### In claude.ai (manual)

There are no subagents on claude.ai, so you (or another instance of Claude) work through the evals one at a time:

1. Read the skill's `SKILL.md`
2. Take the prompt from each eval and produce the output as the skill prescribes
3. For each expectation, check whether your output satisfies it
4. Record results in a markdown file or feedback JSON

This is less rigorous (you wrote the test and the answer; conflict of interest) but it's still a useful sanity check.

---

## Running the Benchmark Mode

To get statistical confidence with variance analysis:

```bash
python -m scripts.aggregate_benchmark \
  --evals /path/to/behavioral-evals.json \
  --skill-path /path/to/group-synastry-private/plugins/group-synastry/skills/group-synastry \
  --runs-per-config 3 \
  --include-baseline true
```

This runs each eval 3 times **with the skill** and 3 times **without** (naked Claude, no skill loaded). Output:

```json
{
  "with_skill":    {"pass_rate": {"mean": 0.85, "stddev": 0.05}},
  "without_skill": {"pass_rate": {"mean": 0.20, "stddev": 0.10}},
  "delta": {"pass_rate": "+0.65"}
}
```

For a specialized skill like `group-synastry`, the lift over baseline should be very large (Claude can't compute Vimshottari Dasha or BaZi pillars from priors). If lift is small, something is wrong with either the skill or the evals.

---

## Coverage Matrix

| Capability area | Trigger evals | Behavioral evals |
|---|---|---|
| Core synastry | ✓ (5) | ✓ (eval 7) |
| Composite (midpoint + Davison) | ✓ (2) | ✓ (evals 8, 9) |
| Western tropical natal | ✓ (4) | ✓ (eval 4) |
| Vedic / Jyotish | ✓ (3) | ✓ (eval 5) |
| Chinese BaZi | ✓ (2) | ✓ (eval 6) |
| Hellenistic | ✓ (1) | ✓ (eval 16) |
| Predictive (transits, returns, dasha) | ✓ (5) | ✓ (evals 14, 15, 16) |
| DB management (add, list, update) | ✓ (5) | ✓ (evals 1, 2, 3, 17) |
| Output formats (.docx, .pdf) | ✓ (2) | ✓ (eval 12) |
| Group operations (matrix) | ✓ (1) | ✓ (eval 11) |
| Clarification-first behavior | implicit | ✓ (evals 10, 11) |
| Settings persistence | — | ✓ (eval 18) |
| Missing-person handling | — | ✓ (eval 13) |
| Negative cases (should NOT trigger) | ✓ (20) | — |

---

## Updating the Eval Suite

When the spec changes, the evals should follow. Some examples:

- **New always-included body added to D6** → update behavioral eval 4 and 7 to require it
- **New supported astrological system** → add trigger evals + a behavioral eval
- **Spec §9.4 (clarification rules) changes** → update behavioral evals 10, 11 to match
- **New output format supported** → add behavioral eval; add trigger evals like "make a [format] of X"

Reference data (`reference-charts.json`) should only change when the underlying ephemeris improves, not when the spec changes.

---

## Notes on Reference Data Accuracy

The reference values in `reference-charts.json` were computed with Swiss Ephemeris 2.10 (via `pyswisseph`) using the precise birth coordinates. Tolerances in the assertions:

- Major planet positions: ±1 arcminute
- Asteroid positions (Keplerian fallback): ±2 arcminutes
- House cusps and angles: ±5 arcminutes (sensitive to coordinate precision)
- Solar Return moment: ±5 minutes
- Davison location: ±0.5° (lat/lon midpoint approximation)

A skill that consistently misses by 30+ arcminutes is doing something fundamentally wrong (e.g., computing for the wrong date, using the wrong coordinate system, applying ayanamsa twice). Tighter tolerances would over-fail on legitimate small differences in implementation.

---

*For the spec this eval suite tests against, see [`docs/specs/primary.md`](../docs/specs/primary.md) — the authoritative current-state spec. (The original Phase 1 design spec is archived at `docs/archive/original-spec/spec.md` but is fully superseded; primary.md is the source of truth.)*
