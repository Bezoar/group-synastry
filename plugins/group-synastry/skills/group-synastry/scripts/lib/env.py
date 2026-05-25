"""Environment detection: Claude Code vs Claude.ai sandbox.

Returns paths for the people.json database and chart output files. Per the
primary spec §5.1, Claude.ai uses /mnt/user-data/{uploads,outputs} and Claude
Code uses ~/.config/group-synastry/ + cwd.
"""
from __future__ import annotations

import os
from pathlib import Path


CLAUDE_AI_UPLOADS = Path("/mnt/user-data/uploads")
CLAUDE_AI_OUTPUTS = Path("/mnt/user-data/outputs")

# Bundled Swiss Ephemeris data, shipped with the skill itself. Currently
# contains seas_18.se1 (Chiron, Ceres, Pallas, Juno, Vesta — arcsec accuracy
# 1800–2100). The file is small (~250 KB) so we ship it rather than asking
# the user to fetch it.
BUNDLED_EPHE_DIR = Path(__file__).resolve().parents[2] / "ephe"


def is_claude_ai() -> bool:
    return CLAUDE_AI_UPLOADS.exists() and CLAUDE_AI_OUTPUTS.exists()


def data_dir() -> Path:
    """Directory holding people.json (and settings.json)."""
    if is_claude_ai():
        # Read from uploads if a people.json was uploaded; otherwise we'll
        # write to outputs.
        if (CLAUDE_AI_UPLOADS / "people.json").exists():
            return CLAUDE_AI_UPLOADS
        return CLAUDE_AI_OUTPUTS
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    d = base / "group-synastry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def people_json_path() -> Path:
    """Path to people.json.

    Resolution order:
      1. ``settings.people_db_dir`` if set (created if missing). Lets users
         move the DB out of ``~/.config/group-synastry/`` and into a synced
         cloud folder while keeping ``settings.json`` local.
      2. ``data_dir() / "people.json"`` — the backward-compatible default
         (Claude Code) or the sandbox location (Claude.ai).
    """
    # Lazy import to avoid the env↔settings circular dependency.
    from . import settings  # noqa: WPS433

    configured = settings.get("people_db_dir")
    if configured:
        p = Path(str(configured)).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p / "people.json"
    return data_dir() / "people.json"


def settings_json_path() -> Path:
    if is_claude_ai():
        # Settings persisted to outputs (user must re-upload between sessions)
        return CLAUDE_AI_OUTPUTS / "settings.json"
    return data_dir() / "settings.json"


def outputs_dir() -> Path:
    """Where rendered charts (md/docx/pdf) are written by default.

    Resolution order:
      1. ``settings.default_output_dir`` if set (created if missing). Lets the
         user point output at a synced cloud folder (e.g., Proton Drive) once
         and have every chart land there.
      2. ``/mnt/user-data/outputs`` on Claude.ai (the only writable location
         that round-trips back to the user).
      3. The current working directory in Claude Code.
    """
    # Lazy import: settings.py imports env, so a top-level import would loop.
    from . import settings  # noqa: WPS433 (intentional circular-break)

    configured = settings.get("default_output_dir")
    if configured:
        p = Path(str(configured)).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
    if is_claude_ai():
        CLAUDE_AI_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return CLAUDE_AI_OUTPUTS
    return Path.cwd()


def swisseph_data_paths() -> list[Path]:
    """Directories Swiss Ephemeris should search for .se1 / sefstars.txt.

    Order: user-specific (Claude.ai uploads or ~/.config/group-synastry/ephe)
    first so the user can override bundled files with their own; bundled
    directory last as a guaranteed-present default.
    """
    paths: list[Path] = []
    if is_claude_ai():
        user_ephe = CLAUDE_AI_UPLOADS / "ephe"
    else:
        user_ephe = data_dir() / "ephe"
    if user_ephe.exists():
        paths.append(user_ephe)
    if BUNDLED_EPHE_DIR.exists():
        paths.append(BUNDLED_EPHE_DIR)
    return paths


def swisseph_path_string() -> str:
    """Colon-separated path string suitable for ``swe.set_ephe_path``."""
    return ":".join(str(p) for p in swisseph_data_paths())
