"""Medieval / traditional-European chart computation (CLI).

    medieval.py natal <person_id> [--house-system alcabitius] [--json]

Layers sect, essential dignities, the Lots of Fortune & Spirit, and the almuten
of the Ascendant on top of the natal computation (see lib/medieval.py). Defaults
to Alcabitius houses — the medieval default (docs/specs/medieval.md §1).

Pure computation: this emits no interpretation prose and no citations. The
citation-bearing interpretation layer depends on a verified reference corpus that
is built as a separate sub-project (docs/research/biblio.md); until it exists,
medieval output is numbers and states only, by design.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import medieval  # type: ignore[import-not-found]
    import db  # type: ignore[import-not-found]
else:
    from .lib import medieval
    from . import db


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute medieval / traditional charts.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_natal = sub.add_parser("natal", help="sect, dignities, lots, almuten")
    p_natal.add_argument("ident", help="person id or display_name")
    p_natal.add_argument(
        "--house-system", default=None,
        help="house system (default: alcabitius, the medieval default)",
    )
    p_natal.add_argument("--json", action="store_true",
                         help="print chart as JSON instead of Markdown")

    # Profections are predictive, so they are an explicit subcommand (never part
    # of the default natal output) — satisfying the skill's explicit-ask gate.
    p_prof = sub.add_parser("profection", help="annual profection + lord of the year")
    p_prof.add_argument("ident", help="person id or display_name")
    when = p_prof.add_mutually_exclusive_group(required=True)
    when.add_argument("--age", type=int, help="completed years of age")
    when.add_argument("--on", metavar="YYYY-MM-DD",
                      help="target date; age is computed from the birth date")
    p_prof.add_argument(
        "--house-system", default=None,
        help="house system (default: alcabitius, the medieval default)",
    )
    p_prof.add_argument("--json", action="store_true",
                        help="print as JSON instead of Markdown")

    args = parser.parse_args(argv)
    house_system = args.house_system or medieval.DEFAULT_HOUSE_SYSTEM

    data = db.load()
    person = db.find(data, args.ident)
    if not person:
        print(f"Person not found: {args.ident}", file=sys.stderr)
        return 1

    if __package__ in (None, ""):
        import chart as chart_mod  # type: ignore[import-not-found]
        from render_md import render_medieval, render_profection  # type: ignore[import-not-found]
    else:
        from . import chart as chart_mod
        from .render_md import render_medieval, render_profection

    if args.cmd == "natal":
        mc = medieval.compute_medieval(person, house_system=house_system)
        if args.json:
            print(json.dumps(mc.to_dict(), indent=2, ensure_ascii=False, default=str))
            return 0
        print(render_medieval(mc))
        return 0

    if args.cmd == "profection":
        try:
            age = args.age if args.age is not None else medieval.years_completed(
                person["birth"]["date"], args.on)
            natal = chart_mod.compute_natal(person, house_system=house_system)
            rep = medieval.profection_report(natal, age)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False, default=str))
            return 0
        print(render_profection(natal, rep))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
