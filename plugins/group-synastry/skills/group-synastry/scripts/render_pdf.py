"""Render a chart payload to .pdf via the docx-js renderer + LibreOffice headless.

Strategy (spec §10.3): produce a .docx with render_docx.py, then convert it to
.pdf with ``soffice --headless --convert-to pdf``. LibreOffice is available in
the Claude.ai sandbox out of the box; on Claude Code it may need installing.

CLI:
    render_pdf.py --output out.pdf [--input chart.json] [--kind ...]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import render_docx  # type: ignore[import-not-found]
else:
    from . import render_docx


# Likely soffice locations when it isn't on PATH. Checked in order.
_SOFFICE_FALLBACKS = (
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",   # macOS Application bundle
    "/usr/bin/libreoffice",                                    # Debian/Ubuntu default
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    "/opt/homebrew/bin/soffice",
)


class PdfError(RuntimeError):
    pass


def locate_soffice() -> str:
    on_path = shutil.which("soffice") or shutil.which("libreoffice")
    if on_path:
        return on_path
    for cand in _SOFFICE_FALLBACKS:
        if Path(cand).exists():
            return cand
    raise PdfError(
        "Could not locate LibreOffice (soffice). Install LibreOffice or expose "
        "`soffice` on PATH. Checked PATH and: " + ", ".join(_SOFFICE_FALLBACKS)
    )


DEFAULT_PDF_THEME = "dark"


def render_to_pdf(
    chart: dict,
    output_path: Path,
    *,
    kind: Optional[str] = None,
    style: Optional[dict] = None,
    theme: Optional[str] = None,
    interpretation: Optional[dict] = None,
    soffice_bin: Optional[str] = None,
) -> Path:
    """Render *chart* to *output_path* (.pdf). Returns the output path.

    ``theme`` defaults to ``"dark"`` for PDFs (see DEFAULT_PDF_THEME). PDFs are
    typically viewed on-screen, where a dark palette is easier on the eyes; the
    .docx renderer's default (``light``) is preserved for editing/printing.
    Pass ``theme="light"`` (or ``--theme light`` on the CLI) to override.

    ``interpretation`` is passed straight through to render_docx; see that
    function's docstring for the shape.
    """
    soffice = soffice_bin or locate_soffice()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    effective_theme = theme if theme is not None else DEFAULT_PDF_THEME
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        docx_path = td_path / (output_path.stem + ".docx")
        render_docx.render_to_docx(
            chart, docx_path,
            kind=kind, style=style, theme=effective_theme,
            interpretation=interpretation,
        )
        # LibreOffice writes <stem>.pdf into --outdir.
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(td_path), str(docx_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PdfError(
                f"LibreOffice exited {result.returncode}.\nstderr:\n{result.stderr.strip()}"
            )
        produced = td_path / (docx_path.stem + ".pdf")
        if not produced.exists():
            raise PdfError(
                f"LibreOffice exited 0 but {produced} was not written. "
                f"stdout:\n{result.stdout.strip()}"
            )
        shutil.move(str(produced), str(output_path))
    return output_path


# ---- CLI -----------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=".pdf renderer for group-synastry charts.")
    parser.add_argument("--input", "-i", help="path to chart JSON (default: stdin)")
    parser.add_argument("--output", "-o", required=True, help="path to write .pdf")
    parser.add_argument("--kind", choices=("natal", "synastry", "composite"),
                        help="payload kind (default: auto-detect)")
    parser.add_argument("--style", help="optional path to a style.json override")
    parser.add_argument("--theme", choices=("light", "dark"),
                        help=f"color theme (default: {DEFAULT_PDF_THEME!r} for .pdf)")
    parser.add_argument(
        "--interpretation",
        help="Path to interpretation source (.json or .md sidecar). Appended after the chart data.",
    )
    parser.add_argument(
        "--no-sidecar",
        action="store_true",
        help="Suppress the <output>.interpretation.md sidecar that is otherwise "
             "written when --interpretation is used.",
    )
    parser.add_argument(
        "--cohort",
        help="Route output under cohorts/<id>/. Overrides settings.active_cohort "
             "for this invocation only. Ignored when --output contains a path separator.",
    )
    parser.add_argument(
        "--time-range-pair",
        help="Pair id (e.g. 'alex+casey') for time-range routing; combined with "
             "--time-range-label routes output under "
             "cohorts/<id>/time-range/<pair>/<label>/ and skips the kind subfolder.",
    )
    parser.add_argument(
        "--time-range-label",
        help="Variant label (e.g. 'casey-1700'); see --time-range-pair.",
    )
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

    style = render_docx.load_style(Path(args.style)) if args.style else None
    try:
        effective_kind = args.kind or render_docx.detect_kind(chart)
    except render_docx.RenderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    output_path = render_docx.resolve_output_path(
        args.output, kind=effective_kind, cohort=args.cohort,
        time_range_pair=args.time_range_pair,
        time_range_label=args.time_range_label,
    )
    interpretation: Optional[dict] = None
    if args.interpretation:
        try:
            interpretation = render_docx.parse_interpretation_file(Path(args.interpretation))
        except (OSError, json.JSONDecodeError, render_docx.RenderError) as exc:
            print(f"Error reading --interpretation {args.interpretation}: {exc}", file=sys.stderr)
            return 2
    try:
        out = render_to_pdf(
            chart, output_path,
            kind=effective_kind, style=style, theme=args.theme,
            interpretation=interpretation,
        )
    except (PdfError, render_docx.RenderError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(out)
    if interpretation and not args.no_sidecar:
        title = render_docx._sidecar_title_for(chart, effective_kind)
        sidecar = render_docx.write_interpretation_sidecar(interpretation, out, title=title)
        print(sidecar)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
