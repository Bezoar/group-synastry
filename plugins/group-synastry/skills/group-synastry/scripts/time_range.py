"""Time-range chart generation for people with uncertain birth times.

When a person has ``birth.time_hysteresis_minutes`` set (non-zero), this
module produces a list of time-shifted variants for analysis. The variants
can then be fed to chart.py / synastry.py / composite.py to generate one
set of charts per candidate time.

Strategies:
    min-max          — two variants: minimum and maximum window edges
    every-n-minutes  — fixed step through the window
    asc-boundaries   — adaptive: sample at each Ascendant sign-boundary
                       crossing inside the window

Subcommands:
    time_range.py list <person> --strategy <name> [--step MIN]
        Print the time-shifted variants as JSON (one object per variant).

    time_range.py scan <person>
        Print a window scan: Asc longitude at min/recorded/max and the
        count of Ascendant sign boundaries inside the window.

    time_range.py render <pair> <varied-person> --strategy <name> [--step MIN]
        Drive a full render pipeline: for each variant, compute and render
        cmp/syn/dav charts into ``cohorts/<id>/time-range/<pair>/<label>/``.

The "varied person" is the one whose hysteresis is non-zero; the other
person's time is held at their recorded value. The label uniquely names
the time folder, e.g. ``casey-1700``.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import ephem  # type: ignore[import-not-found]
    from lib.tz import to_julian_day_ut  # type: ignore[import-not-found]
    import db  # type: ignore[import-not-found]
else:
    from .lib import ephem
    from .lib.tz import to_julian_day_ut
    from . import db


SIGN_WIDTH = 30.0  # degrees per zodiac sign


class TimeRangeError(ValueError):
    pass


# ---- time arithmetic -----------------------------------------------------

def _shift_time(date_str: str, time_str: str, minutes: int) -> tuple[str, str]:
    """Return (new_date_str, new_time_str) after shifting by *minutes*.

    Local wall-clock arithmetic — preserves the local-time semantics of the
    birth record. The shifted variant is reinterpreted in the same tz on the
    downstream JD conversion, so DST is handled correctly there.
    """
    base = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    shifted = base + timedelta(minutes=minutes)
    return shifted.strftime("%Y-%m-%d"), shifted.strftime("%H:%M")


def _hhmm_label(time_str: str) -> str:
    """'17:00' → '1700'."""
    return time_str.replace(":", "")


def make_variant(person: dict, minutes_offset: int) -> dict:
    """Return a deep-copied person with the birth time shifted by *minutes_offset*."""
    variant = copy.deepcopy(person)
    birth = variant["birth"]
    new_date, new_time = _shift_time(birth["date"], birth["time"], minutes_offset)
    birth["date"] = new_date
    birth["time"] = new_time
    return variant


def variant_label(person: dict, time_str: str) -> str:
    """e.g. casey at 17:00 → 'casey-1700'."""
    return f"{person['id']}-{_hhmm_label(time_str)}"


# ---- strategies ----------------------------------------------------------

def strategy_min_max(person: dict, hysteresis_min: int) -> list[dict]:
    """Two variants: min and max of the window."""
    return [
        _build_variant_record(person, -hysteresis_min),
        _build_variant_record(person, +hysteresis_min),
    ]


def strategy_every_n_minutes(person: dict, hysteresis_min: int, step_min: int) -> list[dict]:
    """Walk the window at *step_min*. Includes both endpoints and recorded time
    when they fall on the step grid; always includes -hysteresis and +hysteresis.
    """
    if step_min <= 0:
        raise TimeRangeError("step_min must be a positive integer")
    offsets: list[int] = []
    n = -hysteresis_min
    while n < hysteresis_min:
        offsets.append(n)
        n += step_min
    offsets.append(hysteresis_min)  # ensure the max edge is included
    # Dedup while preserving order (e.g. when step divides 2*hysteresis evenly).
    seen: set[int] = set()
    unique = [o for o in offsets if not (o in seen or seen.add(o))]
    return [_build_variant_record(person, o) for o in unique]


def strategy_asc_boundaries(person: dict, hysteresis_min: int) -> list[dict]:
    """Sample at each Ascendant sign-boundary crossing inside the window.

    Always returns at least the recorded time. If the Ascendant crosses N sign
    boundaries inside (-hys, +hys), returns N+1 variants: one just past each
    crossing (so each variant has a stable Asc sign), plus the recorded time
    if it's not already covered.

    Boundary detection uses bisection on local minute offsets — degree-accurate
    enough at one-minute resolution, which is below typical recording precision.
    """
    if hysteresis_min <= 0:
        return [_build_variant_record(person, 0)]

    crossings = _find_asc_sign_crossings(person, hysteresis_min)
    if not crossings:
        return [_build_variant_record(person, 0)]

    # Place one sample in each interval bounded by [-hys, c1, c2, ..., +hys].
    bounds = [-hysteresis_min] + crossings + [hysteresis_min]
    samples: list[int] = []
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        # Take the midpoint of each interval — guarantees we're not on a
        # boundary degree, so the Asc sign is stable for that variant.
        samples.append(int(round((lo + hi) / 2.0)))
    return [_build_variant_record(person, o) for o in samples]


# ---- window scan ---------------------------------------------------------

def _asc_at_offset(person: dict, minutes_offset: int) -> float:
    """Compute the Ascendant ecliptic longitude when the recorded birth time
    is shifted by *minutes_offset*.
    """
    birth = person["birth"]
    new_date, new_time = _shift_time(birth["date"], birth["time"], minutes_offset)
    conv = to_julian_day_ut(new_date, new_time, birth["tz"])
    houses = ephem.calc_houses(conv.julian_day_ut, birth["lat"], birth["lon"])
    return houses.ascendant


def _find_asc_sign_crossings(person: dict, hysteresis_min: int) -> list[int]:
    """Return the sorted minute-offsets within (-hysteresis, +hysteresis) where
    the Ascendant crosses a sign boundary (every 30°).

    Uses a coarse-to-fine scan: walk the window at 5-minute resolution to find
    crossings, then bisect each crossing down to 1-minute precision.
    """
    coarse_step = 5
    offsets = list(range(-hysteresis_min, hysteresis_min + 1, coarse_step))
    if offsets[-1] != hysteresis_min:
        offsets.append(hysteresis_min)
    ascs = [_asc_at_offset(person, o) for o in offsets]
    coarse_crossings: list[tuple[int, int]] = []
    for i in range(len(offsets) - 1):
        if _crosses_sign_boundary(ascs[i], ascs[i + 1]):
            coarse_crossings.append((offsets[i], offsets[i + 1]))
    # Bisect each coarse crossing to minute precision.
    refined: list[int] = []
    for lo, hi in coarse_crossings:
        crossing = _bisect_crossing(person, lo, hi, ascs_at_lo=None)
        if crossing is not None and -hysteresis_min < crossing < hysteresis_min:
            refined.append(crossing)
    return sorted(set(refined))


def _crosses_sign_boundary(asc_a: float, asc_b: float) -> bool:
    """True if the Ascendant moved from one zodiac sign to another between a→b.

    The Ascendant advances forward in time, so we compute the (positive,
    mod-360) angular distance traveled; if that distance plus the partial
    sign of A exceeds 30°, we crossed at least one boundary.
    """
    travel = (asc_b - asc_a) % 360.0
    if travel == 0.0:
        return False
    sign_a = int(asc_a // SIGN_WIDTH)
    sign_b = int(asc_b // SIGN_WIDTH)
    if sign_a == sign_b and travel < SIGN_WIDTH:
        return False
    return True


def _bisect_crossing(
    person: dict, lo_offset: int, hi_offset: int, ascs_at_lo: Optional[float],
) -> Optional[int]:
    """Bisect [lo, hi] to find the minute-offset of the sign boundary."""
    if hi_offset - lo_offset <= 1:
        return hi_offset
    asc_lo = ascs_at_lo if ascs_at_lo is not None else _asc_at_offset(person, lo_offset)
    sign_lo = int(asc_lo // SIGN_WIDTH)
    while hi_offset - lo_offset > 1:
        mid = (lo_offset + hi_offset) // 2
        asc_mid = _asc_at_offset(person, mid)
        sign_mid = int(asc_mid // SIGN_WIDTH)
        if sign_mid == sign_lo:
            lo_offset, asc_lo = mid, asc_mid
        else:
            hi_offset = mid
    return hi_offset


def scan_window(person: dict, hysteresis_min: Optional[int] = None) -> dict:
    """Return a quick scan of the window's Asc behavior for adaptive recommendation.

    Output:
        {
            "person_id": ...,
            "hysteresis_minutes": ...,
            "recorded_time": "HH:MM",
            "asc_at_min": {"longitude": ..., "sign": ...},
            "asc_at_recorded": {"longitude": ..., "sign": ...},
            "asc_at_max": {"longitude": ..., "sign": ...},
            "sign_boundaries_in_window": int,
            "recommendation": str,
        }
    """
    if hysteresis_min is None:
        hysteresis_min = db.get_hysteresis_minutes(person)
    if hysteresis_min <= 0:
        return {
            "person_id": person["id"],
            "hysteresis_minutes": 0,
            "recorded_time": person["birth"]["time"],
            "recommendation": "No hysteresis set; time-range charting not applicable.",
        }
    asc_min = _asc_at_offset(person, -hysteresis_min)
    asc_rec = _asc_at_offset(person, 0)
    asc_max = _asc_at_offset(person, +hysteresis_min)
    boundaries = _find_asc_sign_crossings(person, hysteresis_min)
    return {
        "person_id": person["id"],
        "hysteresis_minutes": hysteresis_min,
        "recorded_time": person["birth"]["time"],
        "asc_at_min": _asc_summary(asc_min),
        "asc_at_recorded": _asc_summary(asc_rec),
        "asc_at_max": _asc_summary(asc_max),
        "sign_boundaries_in_window": len(boundaries),
        "boundary_offsets_minutes": boundaries,
        "recommendation": _recommend(len(boundaries)),
    }


def _asc_summary(lon: float) -> dict:
    sign_idx = int(lon // SIGN_WIDTH)
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    deg_in_sign = lon - sign_idx * SIGN_WIDTH
    return {
        "longitude": round(lon, 4),
        "sign": signs[sign_idx],
        "degree_in_sign": round(deg_in_sign, 2),
    }


def _recommend(n_boundaries: int) -> str:
    if n_boundaries == 0:
        return (
            "0 Ascendant sign boundaries inside the window — the chart's "
            "qualitative reading is stable across the uncertainty. A single "
            "chart at the recorded time is sufficient."
        )
    if n_boundaries == 1:
        return (
            "1 Ascendant sign boundary inside the window — recommend "
            "asc-boundaries strategy (2 variants, one per Asc sign)."
        )
    return (
        f"{n_boundaries} Ascendant sign boundaries inside the window — "
        f"recommend asc-boundaries strategy ({n_boundaries + 1} variants)."
    )


# ---- variant record shape -----------------------------------------------

def _build_variant_record(person: dict, minutes_offset: int) -> dict:
    """Return one variant entry: shifted person + label + offset."""
    shifted = make_variant(person, minutes_offset)
    return {
        "label": variant_label(shifted, shifted["birth"]["time"]),
        "minutes_offset": minutes_offset,
        "time": shifted["birth"]["time"],
        "person": shifted,
    }


# ---- render driver -------------------------------------------------------

def render_pair(
    pair_id: str,
    person_a: dict,
    person_b: dict,
    varied_person: dict,
    other_person: dict,
    variants: list[dict],
    *,
    cohort: Optional[str] = None,
    kinds: tuple[str, ...] = ("synastry", "composite", "davison"),
    python_bin: str = sys.executable,
) -> list[dict]:
    """For each variant of *varied_person*, generate cmp/syn/dav charts.

    Returns a list of result dicts (one per variant) with paths to the
    rendered PDFs and sidecars.

    *pair_id* is the folder name (e.g. ``alex+casey``) — caller chooses the
    canonical ordering. *person_a*/*person_b* are the inputs to the chart
    scripts in their original order (which may differ from the canonical
    pair_id ordering). The *varied_person* must be either *person_a* or
    *person_b*.
    """
    if varied_person["id"] not in (person_a["id"], person_b["id"]):
        raise TimeRangeError(
            f"varied_person '{varied_person['id']}' must be one of the pair members"
        )
    script_dir = Path(__file__).resolve().parent
    results: list[dict] = []
    for v in variants:
        # Substitute the varied person with its time-shifted variant.
        a_in = v["person"] if v["person"]["id"] == person_a["id"] else person_a
        b_in = v["person"] if v["person"]["id"] == person_b["id"] else person_b
        out_paths: dict[str, list[str]] = {}
        for kind in kinds:
            chart_json = _compute_kind_json(script_dir, kind, a_in, b_in, python_bin)
            pdf_name = _kind_filename(kind, pair_id)
            paths = _render_pdf(
                script_dir, chart_json, pdf_name,
                cohort=cohort,
                pair=pair_id, label=v["label"],
                python_bin=python_bin,
            )
            out_paths[kind] = paths
        results.append({"variant": v["label"], "outputs": out_paths})
    return results


def _compute_kind_json(
    script_dir: Path, kind: str, a: dict, b: dict, python_bin: str,
) -> str:
    """Run the appropriate compute script with --json on stdin-friendly people.

    The chart scripts read from the live people.json by id, not from injected
    data, so we have to side-channel the variant. We do this by writing a
    temporary people.json patch via env var, or — simpler — by invoking the
    compute logic directly via Python rather than CLI. That keeps the variant
    in-process and avoids touching the user's DB.
    """
    # In-process compute: import and run directly. Faster than subprocess for
    # the inner loop, and keeps variants isolated from the user's live DB.
    from dataclasses import asdict
    if __package__ in (None, ""):
        sys.path.insert(0, str(script_dir))
        from chart import compute_natal  # type: ignore[import-not-found]
        from synastry import compute_synastry  # type: ignore[import-not-found]
        from composite import midpoint_composite, davison  # type: ignore[import-not-found]
    else:  # pragma: no cover — package-mode invocation isn't expected here
        from .chart import compute_natal
        from .synastry import compute_synastry
        from .composite import midpoint_composite, davison

    if kind == "synastry":
        payload = asdict(compute_synastry(a, b))
    elif kind == "composite":
        payload = asdict(midpoint_composite(a, b))
    elif kind == "davison":
        payload = asdict(davison(a, b))
    elif kind == "natal":
        payload = compute_natal(a).to_dict()
    else:
        raise TimeRangeError(f"Unknown kind: {kind}")
    return json.dumps(payload, default=str)


def _kind_filename(kind: str, pair_id: str) -> str:
    """Map kind → short-prefix filename. Pair is implicit in the directory."""
    a, b = pair_id.split("+", 1)
    base = f"{a}-{b}"
    prefix = {"natal": "", "synastry": "syn-", "composite": "cmp-", "davison": "dav-"}[kind]
    return f"{prefix}{base}.pdf"


def _render_pdf(
    script_dir: Path,
    chart_json: str,
    out_name: str,
    *,
    cohort: Optional[str],
    pair: str,
    label: str,
    python_bin: str,
) -> list[str]:
    """Spawn render_pdf.py for a single chart variant. Returns stdout lines."""
    cmd = [python_bin, str(script_dir / "render_pdf.py"),
           "-o", out_name,
           "--time-range-pair", pair,
           "--time-range-label", label]
    if cohort:
        cmd.extend(["--cohort", cohort])
    proc = subprocess.run(
        cmd, input=chart_json, text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        raise TimeRangeError(
            f"render_pdf.py failed for {out_name} ({label}): "
            f"{proc.stderr.strip()}"
        )
    return [ln for ln in proc.stdout.strip().splitlines() if ln]


# ---- CLI -----------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Time-range chart generation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="Print variants per strategy")
    p_list.add_argument("person", help="person id (or display name)")
    p_list.add_argument("--strategy", required=True,
                        choices=("min-max", "every-n-minutes", "asc-boundaries"))
    p_list.add_argument("--step", type=int, default=15,
                        help="step (minutes) for every-n-minutes (default: 15)")

    p_scan = sub.add_parser("scan", help="Window scan + adaptive recommendation")
    p_scan.add_argument("person")

    p_render = sub.add_parser("render", help="Generate the chart variants end-to-end")
    p_render.add_argument("person_a")
    p_render.add_argument("person_b")
    p_render.add_argument("--varied", help="id of the person whose time varies "
                                            "(default: whichever has hysteresis > 0)")
    p_render.add_argument("--strategy", required=True,
                          choices=("min-max", "every-n-minutes", "asc-boundaries"))
    p_render.add_argument("--step", type=int, default=15)
    p_render.add_argument("--cohort", help="route under cohorts/<id>/ (overrides "
                                            "settings.active_cohort)")
    p_render.add_argument("--kind", action="append",
                          choices=("synastry", "composite", "davison"),
                          help="restrict to these kinds (default: all 3)")

    args = parser.parse_args(argv)
    data = db.load()

    if args.cmd == "list":
        person = db.find(data, args.person)
        if not person:
            print(f"Not found: {args.person}", file=sys.stderr)
            return 1
        hys = db.get_hysteresis_minutes(person)
        if hys <= 0:
            print(f"{person['id']} has no hysteresis set — no variants.",
                  file=sys.stderr)
            return 1
        try:
            variants = _dispatch_strategy(person, hys, args.strategy, args.step)
        except TimeRangeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(variants, indent=2))
        return 0

    if args.cmd == "scan":
        person = db.find(data, args.person)
        if not person:
            print(f"Not found: {args.person}", file=sys.stderr)
            return 1
        print(json.dumps(scan_window(person), indent=2))
        return 0

    if args.cmd == "render":
        a = db.find(data, args.person_a)
        b = db.find(data, args.person_b)
        if not a or not b:
            print(f"Not found: {args.person_a if not a else args.person_b}",
                  file=sys.stderr)
            return 1
        varied = a if (args.varied or "") == a["id"] else (b if (args.varied or "") == b["id"] else None)
        if not varied:
            if db.get_hysteresis_minutes(a) > 0 and db.get_hysteresis_minutes(b) == 0:
                varied = a
            elif db.get_hysteresis_minutes(b) > 0 and db.get_hysteresis_minutes(a) == 0:
                varied = b
            else:
                print("Specify --varied <id> when both or neither person has "
                      "hysteresis set.", file=sys.stderr)
                return 2
        hys = db.get_hysteresis_minutes(varied)
        if hys <= 0:
            print(f"{varied['id']} has no hysteresis set — nothing to do.",
                  file=sys.stderr)
            return 1
        try:
            variants = _dispatch_strategy(varied, hys, args.strategy, args.step)
        except TimeRangeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        pair_id = f"{a['id']}+{b['id']}"
        kinds = tuple(args.kind) if args.kind else ("synastry", "composite", "davison")
        try:
            results = render_pair(
                pair_id, a, b, varied, a if varied is b else b, variants,
                cohort=args.cohort, kinds=kinds,
            )
        except TimeRangeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps({
            "pair": pair_id,
            "varied": varied["id"],
            "strategy": args.strategy,
            "variants": [r["variant"] for r in results],
            "outputs": results,
        }, indent=2))
        return 0

    return 1


def _dispatch_strategy(
    person: dict, hysteresis_min: int, strategy: str, step: int,
) -> list[dict]:
    if strategy == "min-max":
        return strategy_min_max(person, hysteresis_min)
    if strategy == "every-n-minutes":
        return strategy_every_n_minutes(person, hysteresis_min, step)
    if strategy == "asc-boundaries":
        return strategy_asc_boundaries(person, hysteresis_min)
    raise TimeRangeError(f"Unknown strategy: {strategy}")


if __name__ == "__main__":
    raise SystemExit(_main())
