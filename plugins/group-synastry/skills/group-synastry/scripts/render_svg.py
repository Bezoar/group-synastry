"""Render a natal chart to a graphical chart wheel (issue #39).

Reads a natal chart JSON (as emitted by ``chart.py natal <id> --json``) from
``--input`` or stdin and writes a chart wheel. The output format is chosen by
the ``--output`` extension:

* ``.svg`` — the vector wheel (the source of truth; no rasterizer needed).
* ``.png`` — rasterized via Chrome/Chromium or LibreOffice (``--scale`` controls
  resolution; default 2 → a 2000px wheel).
* ``.pdf`` — a single-page PDF of the wheel.

Typical pipeline:
    python chart.py natal alex --json | python render_svg.py -o alex-wheel.svg

Only natal charts are supported; synastry/composite wheels are a follow-up.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import render_docx  # type: ignore[import-not-found]
    from lib import wheel, rasterize  # type: ignore[import-not-found]
else:
    from . import render_docx
    from .lib import wheel, rasterize


def render_wheel_file(
    chart: dict,
    output_path: Path,
    *,
    theme: str = "light",
    aspects: str = "major",
    show_tints: bool = True,
    scale: int = 2,
) -> Path:
    """Render *chart* to *output_path*; format inferred from the suffix."""
    svg = wheel.render_wheel(chart, theme=theme, aspects=aspects, show_tints=show_tints)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    if suffix == ".svg":
        output_path.write_text(svg)
    elif suffix == ".png":
        output_path.write_bytes(rasterize.svg_to_png(svg, scale=scale))
    elif suffix == ".pdf":
        output_path.write_bytes(rasterize.svg_to_pdf(svg))
    else:
        raise ValueError(
            f"Unsupported wheel output extension {suffix!r}; use .svg, .png, or .pdf."
        )
    return output_path


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Graphical natal chart-wheel renderer.")
    parser.add_argument("--input", "-i", help="path to natal chart JSON (default: stdin)")
    parser.add_argument("--output", "-o", required=True, help="path to write (.svg/.png/.pdf)")
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument("--aspects", choices=("major", "all"), default="major",
                        help="which aspects to draw (default: major)")
    parser.add_argument("--no-tints", action="store_true",
                        help="omit the pastel per-sign element tints")
    parser.add_argument("--scale", type=int, default=2,
                        help="PNG resolution multiplier (default: 2 → 2000px)")
    parser.add_argument("--cohort", help="route bare-filename output under cohorts/<id>/")
    parser.add_argument("--time-range-pair")
    parser.add_argument("--time-range-label")
    args = parser.parse_args(argv)

    if args.input:
        try:
            chart = json.loads(Path(args.input).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Error reading {args.input}: {exc}", file=sys.stderr)
            return 2
    else:
        data = sys.stdin.read()
        if not data.strip():
            print("Error: no chart JSON on stdin and no --input given.", file=sys.stderr)
            return 2
        try:
            chart = json.loads(data)
        except json.JSONDecodeError as exc:
            print(f"Error: stdin is not valid JSON: {exc}", file=sys.stderr)
            return 2

    try:
        kind = render_docx.detect_kind(chart)
    except render_docx.RenderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if kind != "natal":
        print(f"Error: chart-wheel rendering supports natal charts only (got {kind}).",
              file=sys.stderr)
        return 1

    output_path = render_docx.resolve_output_path(
        args.output, kind="natal", cohort=args.cohort,
        time_range_pair=args.time_range_pair,
        time_range_label=args.time_range_label,
    )
    try:
        out = render_wheel_file(
            chart, output_path,
            theme=args.theme, aspects=args.aspects,
            show_tints=not args.no_tints, scale=args.scale,
        )
    except (rasterize.RasterizeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
