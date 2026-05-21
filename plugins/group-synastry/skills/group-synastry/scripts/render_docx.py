"""Render a chart payload to .docx via the Node docx-js renderer.

CLI:
    render_docx.py --output out.docx [--input chart.json] [--kind natal|synastry|composite]

Reads chart JSON from ``--input`` or stdin; auto-detects ``kind`` from payload
shape if not given; spawns ``node lib/render_docx.js`` to produce the .docx.

Typical pipeline:
    python chart.py natal alex --json | python render_docx.py -o alex.docx
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import env, settings as _settings  # type: ignore[import-not-found]
else:
    from .lib import env, settings as _settings


SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"
NODE_RENDERER = LIB_DIR / "render_docx.js"
STYLE_PATH = LIB_DIR / "style.json"


def resolve_output_path(
    path_arg: str,
    kind: Optional[str] = None,
    cohort: Optional[str] = None,
    time_range_pair: Optional[str] = None,
    time_range_label: Optional[str] = None,
) -> Path:
    """Resolve a CLI ``--output`` value against ``env.outputs_dir()``.

    Absolute paths are honored as-is; relative paths are placed inside the
    configured output directory.

    When ``path_arg`` is a **bare filename** (no path separator), three optional
    layers of routing apply, in this order:

    1. **Cohort routing.** If *cohort* is passed OR ``settings.active_cohort``
       is set, the path gets a ``cohorts/<cohort-id>/`` prefix.
    2. **Time-range routing.** If BOTH *time_range_pair* (e.g. ``alex+casey``)
       AND *time_range_label* (e.g. ``casey-1700``) are passed, the path gets
       a ``time-range/<pair>/<label>/`` prefix — and the kind subfolder layer
       below is SKIPPED, because time-range output groups all kinds together
       per variant.
    3. **Kind routing.** Otherwise, ``settings.default_output_subfolders[kind]``
       (e.g. ``natal → birth-charts``) is appended.

    Any layer can be inactive. Explicit subdirs in ``--output`` (any path
    separator in the argument) bypass *all* layers — that's the escape hatch.
    """
    p = Path(path_arg).expanduser()
    if p.is_absolute():
        return p
    base = env.outputs_dir()
    if "/" not in path_arg and "\\" not in path_arg:
        # Bare filename — apply cohort + (time-range OR kind) routing.
        effective_cohort = cohort if cohort is not None else _settings.get("active_cohort")
        if effective_cohort:
            base = base / "cohorts" / str(effective_cohort)
        if time_range_pair and time_range_label:
            base = base / "time-range" / str(time_range_pair) / str(time_range_label)
        elif kind:
            sub = _settings.subfolder_for_kind(kind)
            if sub:
                base = base / sub
    return base / p


def parse_interpretation_file(path: Path) -> dict:
    """Load an interpretation source file as ``{"sections": [...]}``.

    Two formats are accepted, auto-detected from the file extension:

    * ``.json`` — the canonical machine-readable shape
      ``{"sections": [{"heading": str, "body": markdown}, ...]}``.
    * ``.md`` — a human-editable sidecar where each ``## heading`` line starts
      a new section and everything between it and the next ``##`` is that
      section's markdown body. Lines at the top before the first ``##``
      (e.g., a ``# Title`` and a sidecar header comment) are skipped.

    The ``.md`` shape is also what :func:`write_interpretation_sidecar` emits
    after a successful render, so the source round-trips: edit the sidecar,
    re-render with ``--interpretation sidecar.md``, and the new prose lands
    in the output document.
    """
    path = Path(path)
    text = path.read_text()
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in (".md", ".markdown"):
        return _parse_interpretation_markdown(text)
    raise RenderError(
        f"--interpretation: unsupported file extension {path.suffix!r}. "
        "Use .json (machine) or .md (human-editable sidecar)."
    )


def _parse_interpretation_markdown(text: str) -> dict:
    sections: list[dict] = []
    current_heading: Optional[str] = None
    current_body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections.append({
                    "heading": current_heading,
                    "body": "\n".join(current_body).strip("\n"),
                })
            current_heading = line[3:].strip()
            current_body = []
        elif current_heading is not None:
            current_body.append(line)
        # else: pre-first-h2 lines (title, sidecar header) are dropped.
    if current_heading is not None:
        sections.append({
            "heading": current_heading,
            "body": "\n".join(current_body).strip("\n"),
        })
    return {"sections": sections}


def write_interpretation_sidecar(interp: dict, output_path: Path, *, title: str = "") -> Path:
    """Write ``<output_path>.interpretation.md`` next to *output_path*.

    The sidecar is plain markdown — human-editable, re-loadable via
    :func:`parse_interpretation_file`. Returns the sidecar path. Existing
    sidecars are overwritten.
    """
    sidecar = output_path.with_suffix("")
    sidecar = sidecar.parent / f"{sidecar.name}.interpretation.md"
    lines: list[str] = []
    if title:
        lines.append(f"# {title}")
        lines.append("")
    lines.append(
        f"_Auto-generated by the group-synastry skill alongside "
        f"`{output_path.name}`. Edit the body markdown freely and re-render "
        f"with `--interpretation {sidecar.name}` to update the document._"
    )
    lines.append("")
    for section in interp.get("sections", []):
        lines.append(f"## {section.get('heading', '').strip()}")
        lines.append("")
        body = section.get("body", "").strip("\n")
        if body:
            lines.append(body)
            lines.append("")
    sidecar.write_text("\n".join(lines))
    return sidecar


class RenderError(RuntimeError):
    pass


def detect_kind(chart: dict) -> str:
    if "overlays_a_in_b" in chart:
        return "synastry"
    if "method" in chart and "points" in chart:
        return "composite"
    if "planets" in chart and "display_name" in chart:
        return "natal"
    raise RenderError(
        "Cannot detect chart kind from payload. Pass --kind natal|synastry|composite."
    )


def load_style(path: Optional[Path] = None) -> dict:
    p = path or STYLE_PATH
    return json.loads(p.read_text())


def render_to_docx(
    chart: dict,
    output_path: Path,
    *,
    kind: Optional[str] = None,
    style: Optional[dict] = None,
    theme: Optional[str] = None,
    interpretation: Optional[dict] = None,
    node_bin: Optional[str] = None,
) -> Path:
    """Render *chart* to *output_path* (.docx). Returns the output path.

    ``theme`` selects a color palette from ``style.themes`` (typically ``light``
    or ``dark``). If unset, ``style.default_theme`` is used (``light`` for
    .docx; .pdf renderer overrides to ``dark`` — see render_pdf.py).

    ``interpretation`` is an optional ``{"sections": [{"heading": str,
    "body": markdown-str}, ...]}`` block. When present, the renderer appends
    an "Interpretation" section after the chart data. The renderer is
    level-agnostic — depth (none/min/max) lives in SKILL.md as guidance for
    how many sections Claude writes.
    """
    if not NODE_RENDERER.exists():
        raise RenderError(f"Node renderer missing: {NODE_RENDERER}")
    node = node_bin or shutil.which("node")
    if not node:
        raise RenderError(
            "Could not locate `node` on PATH. Install Node 20+ "
            "(see plugins/group-synastry/skills/group-synastry/README.md)."
        )
    style = style if style is not None else load_style()
    k = kind or detect_kind(chart)
    # Allow callers to either pass interpretation= or embed it in the chart
    # dict ahead of time (which is what --interpretation FILE on the CLI
    # does — it merges into chart before calling here).
    interp = interpretation if interpretation is not None else chart.get("interpretation")
    payload: dict = {"kind": k, "chart": chart, "style": style}
    if theme is not None:
        payload["theme"] = theme
    if interp is not None:
        payload["interpretation"] = interp
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [node, str(NODE_RENDERER), "--out", str(output_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RenderError(
            f"node render_docx.js exited {result.returncode}.\n"
            f"stderr:\n{result.stderr.strip()}"
        )
    if not output_path.exists():
        raise RenderError(
            f"node render_docx.js exited 0 but {output_path} was not written."
        )
    return output_path


# ---- CLI -----------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=".docx renderer for group-synastry charts.")
    parser.add_argument("--input", "-i", help="path to chart JSON (default: stdin)")
    parser.add_argument("--output", "-o", required=True, help="path to write .docx")
    parser.add_argument("--kind", choices=("natal", "synastry", "composite"),
                        help="payload kind (default: auto-detect)")
    parser.add_argument("--style", help="optional path to a style.json override")
    parser.add_argument("--theme", choices=("light", "dark"),
                        help="color theme (default: style.default_theme, typically 'light')")
    parser.add_argument(
        "--interpretation",
        help='Path to interpretation source: .json ({"sections": [{"heading": str, "body": markdown}, ...]}) '
             "or .md (the sidecar format emitted alongside renders). Appended after the chart data.",
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

    style = load_style(Path(args.style)) if args.style else None
    # Detect kind up front so we can route the output into a kind-specific
    # subfolder (if configured) BEFORE asking the renderer to write.
    try:
        effective_kind = args.kind or detect_kind(chart)
    except RenderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    output_path = resolve_output_path(
        args.output, kind=effective_kind, cohort=args.cohort,
        time_range_pair=args.time_range_pair,
        time_range_label=args.time_range_label,
    )
    interpretation: Optional[dict] = None
    if args.interpretation:
        try:
            interpretation = parse_interpretation_file(Path(args.interpretation))
        except (OSError, json.JSONDecodeError, RenderError) as exc:
            print(f"Error reading --interpretation {args.interpretation}: {exc}", file=sys.stderr)
            return 2
    try:
        out = render_to_docx(
            chart, output_path,
            kind=effective_kind, style=style, theme=args.theme,
            interpretation=interpretation,
        )
    except RenderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(out)
    if interpretation and not args.no_sidecar:
        title = _sidecar_title_for(chart, effective_kind)
        sidecar = write_interpretation_sidecar(interpretation, out, title=title)
        print(sidecar)
    return 0


def _sidecar_title_for(chart: dict, kind: Optional[str]) -> str:
    """Build a friendly H1 for the sidecar (e.g., 'Interpretation: Alex — Natal')."""
    k = kind or detect_kind(chart)
    if k == "natal":
        return f"Interpretation: {chart.get('display_name', 'Chart')} — Natal"
    if k == "synastry":
        return f"Interpretation: Synastry — {chart.get('person_a', 'A')} × {chart.get('person_b', 'B')}"
    if k == "composite":
        method = "Davison" if chart.get("method") == "davison" else "Midpoint Composite"
        return f"Interpretation: {method} — {chart.get('person_a', 'A')} & {chart.get('person_b', 'B')}"
    return "Interpretation"


if __name__ == "__main__":
    raise SystemExit(_main())
