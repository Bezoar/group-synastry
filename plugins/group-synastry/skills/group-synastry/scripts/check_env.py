"""Dependency doctor for the group-synastry skill.

Probes for everything the skill's Python scripts need and reports, per item,
whether it's present and — if not — the exact command to install it. Designed
to be run before the first chart in a session so Claude can guide the user
through any missing setup.

Tiers:
  * core      — required for ANY chart (Python >=3.10, pyswisseph). If a core
                item is missing, the script exits non-zero.
  * optional  — needed only for specific output formats (.docx needs Node +
                a project-local ``npm install``; .pdf needs LibreOffice). Their
                absence never blocks Markdown output.
  * info      — bundled extras (the seas_18.se1 ephemeris file) — reported for
                visibility, never actionable.

CLI:
    check_env.py            human-readable table + a parseable summary line
    check_env.py --json     machine-readable JSON only

Exit code: 0 if all core deps are satisfied, 1 otherwise.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import env  # type: ignore[import-not-found]
else:
    from .lib import env


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REQUIREMENTS = SKILL_DIR / "requirements.txt"
NODE_MODULES = SKILL_DIR / "node_modules"
MIN_PYTHON = (3, 10)

# soffice locations to probe when it isn't on PATH (mirrors render_pdf.py).
_SOFFICE_FALLBACKS = (
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/libreoffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    "/opt/homebrew/bin/soffice",
)


def _pip_install_cmd() -> str:
    # Target the SAME interpreter running this script (env-adaptive: works in
    # the Claude.ai sandbox and against whatever python Claude Code invokes).
    return f'"{sys.executable}" -m pip install -r "{REQUIREMENTS}"'


def _node_install_hint() -> str:
    if sys.platform == "darwin":
        return "brew install node"
    if sys.platform.startswith("linux"):
        return "sudo apt-get install -y nodejs npm   # or your distro's package"
    return "install Node 20+ from https://nodejs.org/"


def _soffice_install_hint() -> str:
    if sys.platform == "darwin":
        return "brew install --cask libreoffice"
    if sys.platform.startswith("linux"):
        return "sudo apt-get install -y libreoffice"
    return "install LibreOffice from https://www.libreoffice.org/"


def _locate_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    for cand in _SOFFICE_FALLBACKS:
        if Path(cand).exists():
            return cand
    return None


def gather() -> list[dict]:
    """Return a list of check records: {key, label, tier, ok, detail, fix}."""
    checks: list[dict] = []

    # --- core: Python version --------------------------------------------
    pyok = sys.version_info[:2] >= MIN_PYTHON
    checks.append({
        "key": "python",
        "label": f"Python {sys.version_info.major}.{sys.version_info.minor}",
        "tier": "core",
        "ok": pyok,
        "detail": f"need >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
        "fix": None if pyok else f"install Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+",
    })

    # --- core: pyswisseph -------------------------------------------------
    spec = importlib.util.find_spec("swisseph")
    swe_detail = "Swiss Ephemeris bindings"
    if spec is not None:
        try:  # best-effort version string
            import swisseph as _swe  # noqa: WPS433 (local import is intentional)
            swe_detail = f"pyswisseph {getattr(_swe, 'version', '?')}"
        except Exception:  # pragma: no cover - present but unimportable
            swe_detail = "pyswisseph (present)"
    checks.append({
        "key": "pyswisseph",
        "label": "pyswisseph",
        "tier": "core",
        "ok": spec is not None,
        "detail": swe_detail,
        "fix": None if spec is not None else _pip_install_cmd(),
    })

    # --- optional: Node (for .docx) --------------------------------------
    node = shutil.which("node")
    checks.append({
        "key": "node",
        "label": "Node.js",
        "tier": "optional",
        "ok": node is not None,
        "detail": "needed for .docx output" if node is None else node,
        "fix": None if node else _node_install_hint(),
    })

    # --- optional: project node_modules (for .docx) ----------------------
    have_modules = NODE_MODULES.is_dir()
    checks.append({
        "key": "node_modules",
        "label": "node_modules (docx, marked)",
        "tier": "optional",
        "ok": have_modules,
        "detail": "needed for .docx output",
        "fix": None if have_modules else f'(cd "{SKILL_DIR}" && npm install)',
    })

    # --- optional: LibreOffice (for .pdf) --------------------------------
    soffice = _locate_soffice()
    checks.append({
        "key": "soffice",
        "label": "LibreOffice (soffice)",
        "tier": "optional",
        "ok": soffice is not None,
        "detail": "needed for .pdf output" if soffice is None else soffice,
        "fix": None if soffice else _soffice_install_hint(),
    })

    # --- info: bundled ephemeris file ------------------------------------
    seas = env.BUNDLED_EPHE_DIR / "seas_18.se1"
    checks.append({
        "key": "seas_18",
        "label": "bundled seas_18.se1",
        "tier": "info",
        "ok": seas.exists(),
        "detail": "arcminute Chiron/Ceres (ships with the skill)",
        "fix": None,
    })

    return checks


def core_satisfied(checks: list[dict]) -> bool:
    return all(c["ok"] for c in checks if c["tier"] == "core")


def render_human(checks: list[dict]) -> str:
    on_ai = env.is_claude_ai()
    lines = ["group-synastry environment check"]
    width = max(len(c["label"]) for c in checks)
    for c in checks:
        mark = "OK     " if c["ok"] else "MISSING"
        tier = "" if c["tier"] == "info" else f"  ({c['tier']})"
        line = f"  [{mark}] {c['label']:<{width}}  {c['detail']}{tier}"
        lines.append(line)
        if not c["ok"] and c["fix"]:
            lines.append(f"           ↳ {c['fix']}")
    core_ok = core_satisfied(checks)
    lines.append("")
    lines.append(f"Core dependencies satisfied: {'YES' if core_ok else 'NO'}")
    lines.append(
        f"Environment: {'Claude.ai sandbox' if on_ai else 'Claude Code (local machine)'}"
    )
    # Parseable summary line for the skill to act on without reparsing the table.
    summary = " ".join(f"{c['key']}={'ok' if c['ok'] else 'missing'}" for c in checks)
    lines.append(f"SUMMARY core_ok={'true' if core_ok else 'false'} {summary}")
    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dependency doctor for group-synastry.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = parser.parse_args(argv)

    checks = gather()
    core_ok = core_satisfied(checks)
    if args.json:
        print(json.dumps({
            "core_satisfied": core_ok,
            "is_claude_ai": env.is_claude_ai(),
            "checks": checks,
        }, indent=2))
    else:
        print(render_human(checks))
    return 0 if core_ok else 1


if __name__ == "__main__":
    raise SystemExit(_main())
