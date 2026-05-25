"""User preferences persisted to ``settings.json``.

Stores cross-session defaults set by the user (eval 18 / primary spec §4.1) so
the skill doesn't re-ask the same clarifying question every time. The file lives
next to ``people.json`` (see ``env.settings_json_path``).

The authoritative set of recognized keys is ``KNOWN_KEYS`` below (documented in
primary spec §8); the block here is just an illustrative shape::

    {
      "version": 1,
      "default_house_system": "whole-sign",   # optional; key in HOUSE_SYSTEM_CODES
      "default_ayanamsa": "lahiri",           # optional
      "default_output_format": "markdown",    # optional: markdown | docx | pdf
      "updated_at": "2026-05-10T22:14:00Z"
    }

Only keys explicitly listed here are read; unknown keys round-trip on write
so a forward-compat upgrade doesn't drop user data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ""):
    import env  # type: ignore[import-not-found]
else:
    from . import env


SCHEMA_VERSION = 1

KNOWN_KEYS = {
    "default_house_system",
    "default_ayanamsa",
    "default_output_format",
    "default_output_dir",
    "default_output_subfolders",
    "default_interpretation_level",
    "default_zodiac",
    "people_db_dir",
    "active_cohort",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load() -> dict:
    path = env.settings_json_path()
    if not path.exists():
        return {"version": SCHEMA_VERSION}
    data = json.loads(path.read_text())
    data.setdefault("version", SCHEMA_VERSION)
    return data


def save(data: dict) -> Path:
    data["version"] = SCHEMA_VERSION
    data["updated_at"] = _now_iso()
    path = env.settings_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return path


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set_pref(key: str, value: Any) -> dict:
    if key not in KNOWN_KEYS:
        raise ValueError(
            f"Unknown setting '{key}'. Known keys: {sorted(KNOWN_KEYS)}"
        )
    data = load()
    data[key] = value
    save(data)
    return data


def clear(key: str) -> dict:
    data = load()
    data.pop(key, None)
    save(data)
    return data


def default_house_system(fallback: str = "placidus") -> str:
    return get("default_house_system", fallback)


def subfolder_for_kind(kind: str) -> Optional[str]:
    """Look up the configured output subfolder for a chart *kind*.

    Returns the subfolder name (relative, no leading slash) or ``None`` if no
    routing is configured for this kind. The setting shape is::

        "default_output_subfolders": {
            "natal":     "birth-charts",
            "synastry":  "synastry",
            "composite": "synastry"
        }

    The render scripts apply this to bare-filename ``--output`` arguments so
    users can organize a single output directory by chart kind without having
    to repeat the subfolder on every command line.
    """
    mapping = get("default_output_subfolders") or {}
    if not isinstance(mapping, dict):
        return None
    sub = mapping.get(kind)
    if isinstance(sub, str) and sub.strip():
        return sub.strip().strip("/").strip("\\") or None
    return None


# ---- CLI -----------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Read/write skill settings.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("path")
    sub.add_parser("show")
    p_get = sub.add_parser("get"); p_get.add_argument("key")
    p_set = sub.add_parser("set"); p_set.add_argument("key"); p_set.add_argument("value")
    p_clr = sub.add_parser("clear"); p_clr.add_argument("key")
    args = parser.parse_args(argv)

    if args.cmd == "path":
        print(env.settings_json_path())
        return 0
    if args.cmd == "show":
        print(json.dumps(load(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "get":
        val = get(args.key)
        if val is None:
            return 1
        print(val)
        return 0
    if args.cmd == "set":
        # Try to JSON-decode the value so dict/list/bool/number settings work
        # ergonomically from the shell. Fall back to plain string when the
        # value isn't valid JSON (e.g., `set default_house_system whole-sign`).
        try:
            value: Any = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        try:
            set_pref(args.key, value)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(load(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "clear":
        clear(args.key)
        print(json.dumps(load(), indent=2, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
