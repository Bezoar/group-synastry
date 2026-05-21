"""people.json CRUD plus a small CLI.

CLI:
    db.py list                                — list all people
    db.py show <id>                            — print one person as JSON
    db.py add --json <inline>                  — add a person (JSON object)
    db.py update <id> --json <patch>           — patch fields in birth/tags
    db.py remove <id>                          — remove a person
    db.py path                                 — print database path

The schema rules (spec §6.1):
  - id: lowercase ASCII, unique
  - tz: must be IANA — abbreviations rejected
  - lat/lon: signed decimals
  - time_accuracy: exact | approximate | noon-default | unknown
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Allow direct invocation (python skill/scripts/db.py …) by inserting parent.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib import env  # type: ignore[import-not-found]
    from lib.tz import normalize_tz, TZError  # type: ignore[import-not-found]
else:
    from .lib import env
    from .lib.tz import normalize_tz, TZError


SCHEMA_VERSION = 2
VALID_TIME_ACCURACY = {"exact", "approximate", "noon-default", "unknown"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class DBError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "person"


def load() -> dict:
    """Load people.json. Accepts both v1 (people only) and v2 (people + cohorts)
    transparently — v1 files are read in-memory as if they had an empty
    cohorts list, and become v2 on the next save (implicit upgrade)."""
    path = env.people_json_path()
    if not path.exists():
        return {
            "version": SCHEMA_VERSION,
            "updated_at": _now_iso(),
            "people": [],
            "cohorts": [],
        }
    data = json.loads(path.read_text())
    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("people", [])
    data.setdefault("cohorts", [])
    return data


def save(data: dict) -> Path:
    data["updated_at"] = _now_iso()
    data["version"] = SCHEMA_VERSION
    data.setdefault("cohorts", [])
    path = env.people_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return path


def find(data: dict, ident: str) -> Optional[dict]:
    ident_l = ident.lower()
    for p in data["people"]:
        if p["id"].lower() == ident_l or p.get("display_name", "").lower() == ident_l:
            return p
    return None


def list_people(data: dict) -> list[dict]:
    return data["people"]


# ---- cohorts -------------------------------------------------------------

def find_cohort(data: dict, ident: str) -> Optional[dict]:
    ident_l = ident.lower()
    for c in data.get("cohorts", []):
        if c["id"].lower() == ident_l or c.get("display_name", "").lower() == ident_l:
            return c
    return None


def list_cohorts(data: dict) -> list[dict]:
    return data.get("cohorts", [])


def cohort_add(data: dict, cohort: dict) -> dict:
    """Create a new cohort. The input may include ``members``: a list of
    existing person ids. Each must already be in ``data["people"]``."""
    if "display_name" not in cohort:
        raise DBError("Cohort display_name is required.")
    cid = cohort.get("id") or _slug(cohort["display_name"])
    if not ID_RE.match(cid):
        raise DBError(f"Cohort id '{cid}' must be lowercase ASCII alphanumerics + dashes/underscores")
    if find_cohort(data, cid):
        raise DBError(f"A cohort with id '{cid}' already exists.")
    members = list(cohort.get("members") or [])
    for m in members:
        if not find(data, m):
            raise DBError(f"Cannot add member '{m}': no such person.")
    new_cohort = {
        "id": cid,
        "display_name": cohort["display_name"],
        "description": cohort.get("description", ""),
        "created_at": _now_iso(),
        "members": [find(data, m)["id"] for m in members],
    }
    data.setdefault("cohorts", []).append(new_cohort)
    return new_cohort


def cohort_update(data: dict, ident: str, patch: dict) -> dict:
    cohort = find_cohort(data, ident)
    if not cohort:
        raise DBError(f"No cohort with id/display_name matching '{ident}'.")
    if "display_name" in patch:
        cohort["display_name"] = patch["display_name"]
    if "description" in patch:
        cohort["description"] = patch["description"]
    if "members" in patch:
        members = list(patch["members"])
        for m in members:
            if not find(data, m):
                raise DBError(f"Cannot set member '{m}': no such person.")
        cohort["members"] = [find(data, m)["id"] for m in members]
    return cohort


def cohort_remove(data: dict, ident: str) -> dict:
    cohort = find_cohort(data, ident)
    if not cohort:
        raise DBError(f"No cohort with id/display_name matching '{ident}'.")
    data["cohorts"] = [c for c in data.get("cohorts", []) if c["id"] != cohort["id"]]
    return cohort


def cohort_add_member(data: dict, cohort_ident: str, person_ident: str) -> dict:
    cohort = find_cohort(data, cohort_ident)
    if not cohort:
        raise DBError(f"No cohort with id/display_name matching '{cohort_ident}'.")
    person = find(data, person_ident)
    if not person:
        raise DBError(f"No person with id/display_name matching '{person_ident}'.")
    pid = person["id"]
    if pid not in cohort.get("members", []):
        cohort.setdefault("members", []).append(pid)
    return cohort


def cohort_remove_member(data: dict, cohort_ident: str, person_ident: str) -> dict:
    cohort = find_cohort(data, cohort_ident)
    if not cohort:
        raise DBError(f"No cohort with id/display_name matching '{cohort_ident}'.")
    person = find(data, person_ident)
    if not person:
        raise DBError(f"No person with id/display_name matching '{person_ident}'.")
    pid = person["id"]
    cohort["members"] = [m for m in cohort.get("members", []) if m != pid]
    return cohort


def cohort_migrate(data: dict, cohort_id: str, display_name: Optional[str] = None,
                   description: str = "") -> dict:
    """One-shot upgrade: create *cohort_id* and add ALL existing people to it.

    Useful for users who had a v1 DB representing a single logical group and
    are migrating to the v2 schema. Raises DBError if a cohort with that id
    already exists or if there are no people in the DB.
    """
    if find_cohort(data, cohort_id):
        raise DBError(
            f"Cohort '{cohort_id}' already exists; nothing to migrate. Use "
            f"'cohort add-member' to add individuals."
        )
    people = list_people(data)
    if not people:
        raise DBError("No people in the database to migrate. Add people first.")
    return cohort_add(data, {
        "id": cohort_id,
        "display_name": display_name or cohort_id.title(),
        "description": description,
        "members": [p["id"] for p in people],
    })


def validate_birth(birth: dict) -> dict:
    """Return a normalized birth dict; raise DBError on invalid input."""
    required = ("date", "time", "tz", "lat", "lon")
    missing = [k for k in required if k not in birth or birth[k] in ("", None)]
    if missing:
        raise DBError(f"Missing required birth fields: {missing}")
    out = dict(birth)
    # Validate date / time
    try:
        datetime.strptime(f"{out['date']} {out['time']}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise DBError(f"Invalid date/time '{out['date']} {out['time']}': {exc}") from exc
    try:
        out["tz"] = normalize_tz(out["tz"])
    except TZError as exc:
        raise DBError(str(exc)) from exc
    try:
        out["lat"] = float(out["lat"])
        out["lon"] = float(out["lon"])
    except (TypeError, ValueError) as exc:
        raise DBError(f"lat/lon must be numeric: {exc}") from exc
    if not -90.0 <= out["lat"] <= 90.0:
        raise DBError(f"lat out of range: {out['lat']}")
    if not -180.0 <= out["lon"] <= 180.0:
        raise DBError(f"lon out of range: {out['lon']}")
    accuracy = out.get("time_accuracy", "exact")
    if accuracy not in VALID_TIME_ACCURACY:
        raise DBError(
            f"time_accuracy must be one of {sorted(VALID_TIME_ACCURACY)}; "
            f"got '{accuracy}'."
        )
    out["time_accuracy"] = accuracy
    if "time_hysteresis_minutes" in out:
        try:
            hys = int(out["time_hysteresis_minutes"])
        except (TypeError, ValueError) as exc:
            raise DBError(
                f"time_hysteresis_minutes must be an integer: {exc}"
            ) from exc
        if hys < 0:
            raise DBError(f"time_hysteresis_minutes must be >= 0; got {hys}")
        if hys > 0:
            out["time_hysteresis_minutes"] = hys
        else:
            out.pop("time_hysteresis_minutes")
    return out


def get_hysteresis_minutes(person: dict) -> int:
    """Return the birth-time uncertainty half-width in minutes, or 0 if unset.

    The field is the half-width: a value of 60 means the recorded time has
    uncertainty ±60 min (total window of 2 hours).
    """
    return int(person.get("birth", {}).get("time_hysteresis_minutes", 0) or 0)


def add(data: dict, person: dict) -> dict:
    if "display_name" not in person:
        raise DBError("display_name is required.")
    pid = person.get("id") or _slug(person["display_name"])
    if not ID_RE.match(pid):
        raise DBError(f"id '{pid}' must be lowercase ASCII alphanumerics + dashes/underscores")
    if find(data, pid):
        raise DBError(f"A person with id '{pid}' already exists.")
    person["id"] = pid
    person["birth"] = validate_birth(person.get("birth", {}))
    person.setdefault("tags", [])
    person["added_at"] = _now_iso()
    data["people"].append(person)
    return person


def update(data: dict, ident: str, patch: dict) -> dict:
    person = find(data, ident)
    if not person:
        raise DBError(f"No person with id/display_name matching '{ident}'.")
    if "display_name" in patch:
        person["display_name"] = patch["display_name"]
    if "tags" in patch:
        person["tags"] = list(patch["tags"])
    if "birth" in patch:
        merged = {**person.get("birth", {}), **patch["birth"]}
        person["birth"] = validate_birth(merged)
    return person


def remove(data: dict, ident: str) -> dict:
    person = find(data, ident)
    if not person:
        raise DBError(f"No person with id/display_name matching '{ident}'.")
    data["people"] = [p for p in data["people"] if p["id"] != person["id"]]
    return person


# ---- CLI -----------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="people.json CRUD")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("path")
    sub.add_parser("list")
    p_show = sub.add_parser("show"); p_show.add_argument("ident")
    p_add = sub.add_parser("add"); p_add.add_argument("--json", required=True)
    p_up = sub.add_parser("update"); p_up.add_argument("ident"); p_up.add_argument("--json", required=True)
    p_rm = sub.add_parser("remove"); p_rm.add_argument("ident")

    # Cohort subcommands — `db.py cohort <subcmd>`.
    p_cohort = sub.add_parser("cohort", help="manage cohorts (groups of people)")
    csub = p_cohort.add_subparsers(dest="cohort_cmd", required=True)
    csub.add_parser("list")
    cshow = csub.add_parser("show"); cshow.add_argument("ident")
    cadd = csub.add_parser("add"); cadd.add_argument("--json", required=True)
    cup = csub.add_parser("update"); cup.add_argument("ident"); cup.add_argument("--json", required=True)
    crm = csub.add_parser("remove"); crm.add_argument("ident")
    cam = csub.add_parser("add-member"); cam.add_argument("cohort_ident"); cam.add_argument("person_ident")
    crmm = csub.add_parser("remove-member"); crmm.add_argument("cohort_ident"); crmm.add_argument("person_ident")
    csa = csub.add_parser("set-active"); csa.add_argument("ident")
    cmig = csub.add_parser("migrate", help="one-shot v1→v2: create cohort + add ALL existing people")
    cmig.add_argument("--name", required=True, help="cohort id (lowercase ASCII, dashes/underscores)")
    cmig.add_argument("--display", help="display name (defaults to title-case of --name)")
    cmig.add_argument("--description", default="")

    args = parser.parse_args(argv)

    if args.cmd == "path":
        print(env.people_json_path())
        return 0
    data = load()
    try:
        if args.cmd == "list":
            for p in data["people"]:
                print(f"{p['id']:<15} {p.get('display_name','')}  {p['birth']['date']} {p['birth']['time']} {p['birth']['tz']}")
            return 0
        if args.cmd == "show":
            person = find(data, args.ident)
            if not person:
                print(f"Not found: {args.ident}", file=sys.stderr)
                return 1
            print(json.dumps(person, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "add":
            person = add(data, json.loads(args.json))
            save(data)
            print(json.dumps(person, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "update":
            person = update(data, args.ident, json.loads(args.json))
            save(data)
            print(json.dumps(person, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "remove":
            person = remove(data, args.ident)
            save(data)
            print(f"Removed: {person['id']}")
            return 0
        if args.cmd == "cohort":
            return _cohort_dispatch(data, args)
    except (DBError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 1


def _cohort_dispatch(data: dict, args) -> int:
    """Sub-dispatcher for `db.py cohort ...` commands."""
    sub = args.cohort_cmd
    if sub == "list":
        for c in list_cohorts(data):
            n = len(c.get("members", []))
            print(f"{c['id']:<15} {c.get('display_name',''):<25}  {n} member{'s' if n != 1 else ''}")
        return 0
    if sub == "show":
        cohort = find_cohort(data, args.ident)
        if not cohort:
            print(f"Cohort not found: {args.ident}", file=sys.stderr)
            return 1
        print(json.dumps(cohort, indent=2, ensure_ascii=False))
        return 0
    if sub == "add":
        cohort = cohort_add(data, json.loads(args.json))
        save(data)
        print(json.dumps(cohort, indent=2, ensure_ascii=False))
        return 0
    if sub == "update":
        cohort = cohort_update(data, args.ident, json.loads(args.json))
        save(data)
        print(json.dumps(cohort, indent=2, ensure_ascii=False))
        return 0
    if sub == "remove":
        cohort = cohort_remove(data, args.ident)
        save(data)
        print(f"Removed cohort: {cohort['id']}")
        return 0
    if sub == "add-member":
        cohort = cohort_add_member(data, args.cohort_ident, args.person_ident)
        save(data)
        print(json.dumps(cohort, indent=2, ensure_ascii=False))
        return 0
    if sub == "remove-member":
        cohort = cohort_remove_member(data, args.cohort_ident, args.person_ident)
        save(data)
        print(json.dumps(cohort, indent=2, ensure_ascii=False))
        return 0
    if sub == "set-active":
        cohort = find_cohort(data, args.ident)
        if not cohort:
            print(f"Cohort not found: {args.ident}", file=sys.stderr)
            return 1
        # Import lazily — settings imports env which imports db is fine; settings
        # is imported elsewhere in this module too via env.py's lazy load.
        if __package__ in (None, ""):
            from lib import settings as _settings  # type: ignore[import-not-found]
        else:
            from .lib import settings as _settings
        _settings.set_pref("active_cohort", cohort["id"])
        print(f"Active cohort set to: {cohort['id']}")
        return 0
    if sub == "migrate":
        cohort = cohort_migrate(
            data, args.name,
            display_name=args.display, description=args.description,
        )
        save(data)
        print(json.dumps(cohort, indent=2, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
