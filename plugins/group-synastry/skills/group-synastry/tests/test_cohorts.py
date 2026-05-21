"""Tests for cohort grouping (issue #9).

Covers the v2 DB schema additions, cohort CRUD helpers, member management,
the v1→v2 migrate convenience command, and the transparent-read-of-v1
behavior on load.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import db
from lib import settings, env


SAMPLE_PERSON = {
    "id": "alex",
    "display_name": "Alex",
    "birth": {
        "date": "1988-06-15", "time": "08:20",
        "tz": "America/Chicago",
        "lat": 41.8781, "lon": -87.6298,
        "place_label": "Chicago, IL",
        "time_accuracy": "exact",
    },
    "tags": [],
}

ANOTHER_PERSON = {
    "id": "jordan",
    "display_name": "Jordan",
    "birth": {
        "date": "1991-02-09", "time": "14:45",
        "tz": "America/Denver",
        "lat": 39.7392, "lon": -104.9903,
        "place_label": "Denver, CO",
        "time_accuracy": "exact",
    },
    "tags": [],
}


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point both people.json and settings.json at tmp dirs."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(env, "is_claude_ai", lambda: False)
    # Make sure people_db_dir isn't set globally from a previous test.
    yield tmp_path


def _seed(data: dict, *people: dict) -> None:
    """Add given people dicts into data["people"] without going through CRUD."""
    for p in people:
        data["people"].append(dict(p, added_at="2026-01-01T00:00:00Z"))


# ---- v1 read / v2 write -------------------------------------------------

def test_load_treats_v1_as_v2_with_empty_cohorts(isolated_db, tmp_path):
    """Old v1 files (no cohorts key) read transparently as v2 with empty cohorts."""
    path = env.people_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": 1,
        "people": [dict(SAMPLE_PERSON, added_at="2026-01-01T00:00:00Z")],
    }))
    data = db.load()
    assert data["people"][0]["id"] == "alex"
    assert data["cohorts"] == [], "v1 file should read as empty cohorts list"


def test_save_writes_v2_and_includes_cohorts_key(isolated_db):
    """A round-trip through save() upgrades the schema version even when
    no cohorts have been added — making the next load v2-native."""
    data = db.load()
    _seed(data, SAMPLE_PERSON)
    db.save(data)
    on_disk = json.loads(env.people_json_path().read_text())
    assert on_disk["version"] == 2
    assert on_disk["cohorts"] == []


def test_load_v2_round_trips_intact(isolated_db):
    path = env.people_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": 2,
        "people": [dict(SAMPLE_PERSON, added_at="2026-01-01T00:00:00Z")],
        "cohorts": [{
            "id": "lumina",
            "display_name": "Lumina",
            "description": "Family",
            "created_at": "2026-05-13T00:00:00Z",
            "members": ["alex"],
        }],
    }))
    data = db.load()
    assert len(data["cohorts"]) == 1
    assert data["cohorts"][0]["members"] == ["alex"]


# ---- Cohort CRUD --------------------------------------------------------

def test_cohort_add_creates_with_members(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON, ANOTHER_PERSON)
    cohort = db.cohort_add(data, {
        "id": "lumina",
        "display_name": "Lumina",
        "description": "Family",
        "members": ["alex", "jordan"],
    })
    assert cohort["id"] == "lumina"
    assert set(cohort["members"]) == {"alex", "jordan"}
    assert "created_at" in cohort
    # Confirm it lives in the data dict, not a separate copy.
    assert db.find_cohort(data, "lumina") is cohort


def test_cohort_add_rejects_unknown_member(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON)
    with pytest.raises(db.DBError, match="no such person"):
        db.cohort_add(data, {
            "id": "lumina",
            "display_name": "Lumina",
            "members": ["nobody"],
        })


def test_cohort_add_rejects_duplicate_id(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON)
    db.cohort_add(data, {"id": "lumina", "display_name": "Lumina"})
    with pytest.raises(db.DBError, match="already exists"):
        db.cohort_add(data, {"id": "lumina", "display_name": "Dup"})


def test_cohort_add_rejects_invalid_id(isolated_db):
    data = db.load()
    with pytest.raises(db.DBError, match="lowercase ASCII"):
        db.cohort_add(data, {"id": "Lumina!", "display_name": "x"})


def test_cohort_add_auto_slugs_id_from_display_name(isolated_db):
    data = db.load()
    cohort = db.cohort_add(data, {"display_name": "Work Group"})
    assert cohort["id"] == "work-group"


def test_cohort_update_patches_fields(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON, ANOTHER_PERSON)
    db.cohort_add(data, {"id": "lumina", "display_name": "Lumina", "members": ["alex"]})
    db.cohort_update(data, "lumina", {
        "description": "Now with more detail",
        "members": ["alex", "jordan"],
    })
    c = db.find_cohort(data, "lumina")
    assert c["description"] == "Now with more detail"
    assert set(c["members"]) == {"alex", "jordan"}


def test_cohort_remove_drops_cohort_not_people(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON)
    db.cohort_add(data, {"id": "lumina", "display_name": "Lumina", "members": ["alex"]})
    db.cohort_remove(data, "lumina")
    assert db.find_cohort(data, "lumina") is None
    assert db.find(data, "alex") is not None, "removing cohort must not remove people"


def test_cohort_add_member_and_remove_member(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON, ANOTHER_PERSON)
    db.cohort_add(data, {"id": "lumina", "display_name": "Lumina"})
    db.cohort_add_member(data, "lumina", "alex")
    db.cohort_add_member(data, "lumina", "jordan")
    c = db.find_cohort(data, "lumina")
    assert set(c["members"]) == {"alex", "jordan"}
    db.cohort_remove_member(data, "lumina", "alex")
    assert db.find_cohort(data, "lumina")["members"] == ["jordan"]


def test_cohort_add_member_is_idempotent(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON)
    db.cohort_add(data, {"id": "lumina", "display_name": "Lumina"})
    db.cohort_add_member(data, "lumina", "alex")
    db.cohort_add_member(data, "lumina", "alex")
    assert db.find_cohort(data, "lumina")["members"] == ["alex"]


# ---- Migration ---------------------------------------------------------

def test_cohort_migrate_adds_all_existing_people(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON, ANOTHER_PERSON)
    cohort = db.cohort_migrate(data, "lumina", display_name="Lumina",
                               description="The original group")
    assert cohort["id"] == "lumina"
    assert set(cohort["members"]) == {"alex", "jordan"}
    assert cohort["description"] == "The original group"


def test_cohort_migrate_refuses_when_no_people(isolated_db):
    data = db.load()
    with pytest.raises(db.DBError, match="No people"):
        db.cohort_migrate(data, "lumina")


def test_cohort_migrate_refuses_existing_id(isolated_db):
    data = db.load()
    _seed(data, SAMPLE_PERSON)
    db.cohort_add(data, {"id": "lumina", "display_name": "Lumina"})
    with pytest.raises(db.DBError, match="already exists"):
        db.cohort_migrate(data, "lumina")


# ---- CLI dispatch (smoke) ----------------------------------------------

def test_cli_cohort_add_then_list(isolated_db, capsys):
    """Round-trip through the CLI: add, then list, then show."""
    data = db.load()
    _seed(data, SAMPLE_PERSON)
    db.save(data)
    rc = db._main([
        "cohort", "add",
        "--json", json.dumps({"id": "lumina", "display_name": "Lumina", "members": ["alex"]}),
    ])
    assert rc == 0
    rc = db._main(["cohort", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "lumina" in out
    assert "1 member" in out
    rc = db._main(["cohort", "show", "lumina"])
    assert rc == 0


def test_cli_cohort_set_active_writes_setting(isolated_db, capsys):
    """`db.py cohort set-active lumina` writes settings.active_cohort."""
    data = db.load()
    _seed(data, SAMPLE_PERSON)
    db.cohort_add(data, {"id": "lumina", "display_name": "Lumina"})
    db.save(data)
    rc = db._main(["cohort", "set-active", "lumina"])
    assert rc == 0
    assert settings.get("active_cohort") == "lumina"


# ---- Cohort-aware routing ----------------------------------------------

def test_resolve_output_path_with_active_cohort_routes_under_cohorts(
    isolated_db, tmp_path
):
    import render_docx
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("default_output_subfolders", {
        "natal": "birth-charts",
        "synastry": "synastry",
    })
    settings.set_pref("active_cohort", "lumina")

    # Natal goes under cohorts/lumina/birth-charts/
    assert render_docx.resolve_output_path("alex.pdf", kind="natal") == \
        target / "cohorts" / "lumina" / "birth-charts" / "alex.pdf"

    # Synastry goes under cohorts/lumina/synastry/
    assert render_docx.resolve_output_path("alex-jordan.pdf", kind="synastry") == \
        target / "cohorts" / "lumina" / "synastry" / "alex-jordan.pdf"


def test_resolve_output_path_per_call_cohort_overrides_active(isolated_db, tmp_path):
    import render_docx
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("default_output_subfolders", {"natal": "birth-charts"})
    settings.set_pref("active_cohort", "lumina")

    # Explicit --cohort=workgroup overrides the active lumina.
    assert render_docx.resolve_output_path("alex.pdf", kind="natal", cohort="workgroup") == \
        target / "cohorts" / "workgroup" / "birth-charts" / "alex.pdf"


def test_resolve_output_path_no_cohort_falls_back_to_flat_kind_routing(
    isolated_db, tmp_path
):
    """Without active_cohort or --cohort, behavior matches Phase 2.1: kind only."""
    import render_docx
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("default_output_subfolders", {"natal": "birth-charts"})

    assert render_docx.resolve_output_path("alex.pdf", kind="natal") == \
        target / "birth-charts" / "alex.pdf"


def test_resolve_output_path_explicit_subdir_still_bypasses(isolated_db, tmp_path):
    """Explicit subdir in --output continues to bypass BOTH routing layers."""
    import render_docx
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("active_cohort", "lumina")
    settings.set_pref("default_output_subfolders", {"natal": "birth-charts"})

    assert render_docx.resolve_output_path("custom/alex.pdf", kind="natal") == \
        target / "custom" / "alex.pdf"


def test_resolve_output_path_absolute_bypasses_cohort_routing(isolated_db, tmp_path):
    """Absolute paths bypass cohort routing too."""
    import render_docx
    settings.set_pref("active_cohort", "lumina")
    abs_path = str(tmp_path / "specific" / "alex.pdf")
    assert str(render_docx.resolve_output_path(abs_path, kind="natal")) == abs_path


# ---- people_db_dir override ---------------------------------------------

def test_people_db_dir_setting_relocates_db(isolated_db, tmp_path):
    """When people_db_dir is set, env.people_json_path() points there."""
    new_dir = tmp_path / "synced" / "people"
    settings.set_pref("people_db_dir", str(new_dir))
    p = env.people_json_path()
    assert p == new_dir / "people.json"
    assert new_dir.exists(), "env should create the directory on demand"


def test_people_db_dir_unset_falls_back_to_data_dir(isolated_db, tmp_path):
    """No setting → DB lives under data_dir() as before."""
    p = env.people_json_path()
    assert p == tmp_path / "group-synastry" / "people.json"
