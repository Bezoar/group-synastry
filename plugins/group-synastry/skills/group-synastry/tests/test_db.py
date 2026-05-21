"""DB validation tests — IANA enforcement, lat/lon handling, time_accuracy."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point env.data_dir at a temp directory so tests don't write to ~/."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # env caches nothing, so re-import isn't needed.
    yield


def test_normalize_tz_rejects_abbreviation():
    from lib.tz import normalize_tz, TZError
    with pytest.raises(TZError) as exc:
        normalize_tz("EDT")
    assert "America/New_York" in str(exc.value)


def test_normalize_tz_accepts_iana():
    from lib.tz import normalize_tz
    assert normalize_tz("America/New_York") == "America/New_York"
    assert normalize_tz("Asia/Tokyo") == "Asia/Tokyo"


def test_offset_is_cdt_for_chicago_in_june_1988():
    """Catches the 'stored CST permanently' regression listed in evals/README.md
    (a summer date must resolve to daylight time, not standard)."""
    from lib.tz import offset_at
    assert offset_at("1988-06-15", "08:20", "America/Chicago") == "-05:00"


def test_offset_is_pst_for_la_in_january_1980():
    from lib.tz import offset_at
    assert offset_at("1980-01-01", "18:00", "America/Los_Angeles") == "-08:00"


def test_db_add_normalizes_tz_and_validates():
    import db
    data = db.load()
    person = db.add(data, {
        "display_name": "Alex",
        "birth": {
            "date": "1988-06-15", "time": "08:20", "tz": "America/Chicago",
            "lat": 41.8781, "lon": -87.6298, "time_accuracy": "exact",
        },
    })
    assert person["id"] == "alex"
    assert person["birth"]["tz"] == "America/Chicago"
    assert person["birth"]["lat"] == 41.8781
    assert person["birth"]["lon"] == -87.6298


def test_db_rejects_abbreviation_tz():
    import db
    data = db.load()
    with pytest.raises(db.DBError):
        db.add(data, {
            "display_name": "Bad",
            "birth": {
                "date": "1980-01-01", "time": "12:00", "tz": "EDT",
                "lat": 0.0, "lon": 0.0,
            },
        })


def test_db_rejects_invalid_lat():
    import db
    data = db.load()
    with pytest.raises(db.DBError):
        db.add(data, {
            "display_name": "Bad",
            "birth": {
                "date": "1980-01-01", "time": "12:00", "tz": "UTC",
                "lat": 9999, "lon": 0.0,
            },
        })


def test_db_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    import importlib
    import db
    importlib.reload(db)  # pick up the new XDG path
    data = db.load()
    db.add(data, {
        "display_name": "Sarah",
        "birth": {
            "date": "1990-03-15", "time": "12:00", "tz": "America/Los_Angeles",
            "lat": 37.7749, "lon": -122.4194, "time_accuracy": "unknown",
        },
    })
    db.save(data)
    # Reload from disk
    data2 = db.load()
    sarah = db.find(data2, "sarah")
    assert sarah is not None
    assert sarah["birth"]["time_accuracy"] == "unknown"
    assert sarah["birth"]["tz"] == "America/Los_Angeles"
