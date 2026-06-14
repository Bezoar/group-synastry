"""Vedic (sidereal) chart computation (CLI).

    vedic.py natal <person_id> [--ayanamsa lahiri] [--json]

Sidereal graha positions (Lahiri ayanamsa by default), nakshatra + pada +
Vimshottari lord, and Whole-Sign rasi houses from the sidereal Ascendant.

Computation only — no interpretation prose. The Vimshottari dasha timeline and
the Navamsa (D9) divisional chart are not built yet.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import vedic  # type: ignore[import-not-found]
    import db  # type: ignore[import-not-found]
else:
    from .lib import vedic
    from . import db


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute Vedic (sidereal) charts.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_natal = sub.add_parser("natal", help="sidereal grahas, nakshatras, rasi houses")
    p_natal.add_argument("ident", help="person id or display_name")
    p_natal.add_argument(
        "--ayanamsa", default=None,
        help=f"ayanamsa (default {vedic.DEFAULT_AYANAMSA}; one of {sorted(vedic.AYANAMSAS)})",
    )
    p_natal.add_argument("--json", action="store_true",
                         help="print chart as JSON instead of Markdown")
    args = parser.parse_args(argv)

    mode = args.ayanamsa or vedic.DEFAULT_AYANAMSA

    data = db.load()
    person = db.find(data, args.ident)
    if not person:
        print(f"Person not found: {args.ident}", file=sys.stderr)
        return 1
    try:
        vc = vedic.compute_vedic(person, ayanamsa_mode=mode)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(vc.to_dict(), indent=2, ensure_ascii=False, default=str))
        return 0
    if __package__ in (None, ""):
        from render_md import render_vedic  # type: ignore[import-not-found]
    else:
        from .render_md import render_vedic
    print(render_vedic(vc))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
