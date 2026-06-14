"""Hellenistic astrology chart computation (CLI).

    hellenistic.py natal <person_id> [--house-system whole-sign] [--json]

Reuses ``lib/medieval`` for the shared substrate (sect, lots, triplicities) and
adds Whole-Sign houses (numbered from the rising sign) + the triplicity lords of
the sect light. Defaults to Whole-Sign houses (the Hellenistic standard).

Computation only — no interpretation prose and no citations. Zodiacal Releasing
(the heavy Hellenistic-specific time-lord technique) is not built yet.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import hellenistic  # type: ignore[import-not-found]
    import db  # type: ignore[import-not-found]
else:
    from .lib import hellenistic
    from . import db


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute Hellenistic charts.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_natal = sub.add_parser("natal", help="Whole-Sign houses, sect, lots, triplicity lords")
    p_natal.add_argument("ident", help="person id or display_name")
    p_natal.add_argument(
        "--house-system", default=None,
        help="house system (default: whole-sign, the Hellenistic standard)",
    )
    p_natal.add_argument("--json", action="store_true",
                         help="print chart as JSON instead of Markdown")
    args = parser.parse_args(argv)

    house_system = args.house_system or hellenistic.DEFAULT_HOUSE_SYSTEM

    data = db.load()
    person = db.find(data, args.ident)
    if not person:
        print(f"Person not found: {args.ident}", file=sys.stderr)
        return 1
    hc = hellenistic.compute_hellenistic(person, house_system=house_system)
    if args.json:
        print(json.dumps(hc.to_dict(), indent=2, ensure_ascii=False, default=str))
        return 0
    if __package__ in (None, ""):
        from render_md import render_hellenistic  # type: ignore[import-not-found]
    else:
        from .render_md import render_hellenistic
    print(render_hellenistic(hc))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
