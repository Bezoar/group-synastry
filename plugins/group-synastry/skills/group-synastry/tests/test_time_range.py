"""Tests for the time-range / birth-time hysteresis feature (issue #12).

Covers:
- the new ``birth.time_hysteresis_minutes`` field (round-trip, validation,
  default-zero behavior)
- the three strategies (min-max, every-n-minutes, asc-boundaries)
- the routing layer (cohorts/<id>/time-range/<pair>/<label>/)
- the scan_window adaptive helper

Subjects are fictional. CASEY has an uncertain birth time (±60 min) whose
window crosses exactly one Ascendant sign boundary (Sagittarius → Capricorn);
ALEX has an exact time (zero hysteresis).
"""
from __future__ import annotations

import copy
import json

import pytest

import db
import render_docx
import time_range
from lib import env, settings


CASEY = {
    "id": "casey",
    "display_name": "Casey",
    "birth": {
        "date": "1984-07-11", "time": "18:00",
        "tz": "America/Los_Angeles",
        "lat": 32.7157, "lon": -117.1611,
        "place_label": "San Diego, CA",
        "time_accuracy": "approximate",
        "time_hysteresis_minutes": 60,
    },
    "tags": [],
}

ALEX = {
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


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point both people.json and settings.json at tmp dirs."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(env, "is_claude_ai", lambda: False)
    yield tmp_path


# ---- schema: time_hysteresis_minutes ------------------------------------

def test_hysteresis_field_round_trip(isolated_db):
    data = db.load()
    db.add(data, copy.deepcopy(CASEY))
    db.save(data)
    reloaded = db.load()
    p = db.find(reloaded, "casey")
    assert p["birth"]["time_hysteresis_minutes"] == 60


def test_hysteresis_default_zero_when_absent(isolated_db):
    data = db.load()
    db.add(data, copy.deepcopy(ALEX))
    db.save(data)
    reloaded = db.load()
    p = db.find(reloaded, "alex")
    # Field is not stored when 0 — db.get_hysteresis_minutes() resolves it.
    assert "time_hysteresis_minutes" not in p["birth"]
    assert db.get_hysteresis_minutes(p) == 0


def test_hysteresis_zero_is_not_persisted(isolated_db):
    """Explicit 0 round-trips but isn't stored, to keep records clean."""
    data = db.load()
    person = copy.deepcopy(ALEX)
    person["birth"]["time_hysteresis_minutes"] = 0
    db.add(data, person)
    db.save(data)
    reloaded = db.load()
    p = db.find(reloaded, "alex")
    assert "time_hysteresis_minutes" not in p["birth"]


def test_hysteresis_negative_rejected(isolated_db):
    data = db.load()
    person = copy.deepcopy(CASEY)
    person["birth"]["time_hysteresis_minutes"] = -10
    with pytest.raises(db.DBError, match=">= 0"):
        db.add(data, person)


def test_hysteresis_non_numeric_rejected(isolated_db):
    data = db.load()
    person = copy.deepcopy(CASEY)
    person["birth"]["time_hysteresis_minutes"] = "an hour"
    with pytest.raises(db.DBError, match="must be an integer"):
        db.add(data, person)


# ---- strategies ---------------------------------------------------------

def test_strategy_min_max_returns_two_endpoints():
    variants = time_range.strategy_min_max(CASEY, 60)
    assert len(variants) == 2
    assert variants[0]["minutes_offset"] == -60
    assert variants[1]["minutes_offset"] == +60
    assert variants[0]["time"] == "17:00"
    assert variants[1]["time"] == "19:00"
    assert variants[0]["label"] == "casey-1700"
    assert variants[1]["label"] == "casey-1900"


def test_strategy_every_n_minutes_includes_both_endpoints():
    variants = time_range.strategy_every_n_minutes(CASEY, 60, 30)
    offsets = [v["minutes_offset"] for v in variants]
    assert offsets[0] == -60
    assert offsets[-1] == +60
    # Step 30 across ±60 → 5 unique points: -60, -30, 0, 30, 60
    assert offsets == [-60, -30, 0, 30, 60]


def test_strategy_every_n_minutes_rejects_zero_step():
    with pytest.raises(time_range.TimeRangeError):
        time_range.strategy_every_n_minutes(CASEY, 60, 0)


def test_strategy_asc_boundaries_returns_one_variant_per_sign():
    """Casey's window contains exactly one Asc sign boundary (Sgr → Cap)."""
    variants = time_range.strategy_asc_boundaries(CASEY, 60)
    # Expect 2 samples (one per Asc sign interval).
    assert len(variants) == 2
    # Each variant's Asc should fall in a distinct sign.
    signs = []
    for v in variants:
        asc = time_range._asc_at_offset(v["person"], 0)
        signs.append(int(asc // 30.0))
    assert signs[0] != signs[1], "asc-boundaries variants should bracket the sign change"


def test_strategy_asc_boundaries_handles_window_with_no_crossings():
    """A small enough window should produce no boundary crossings → 1 variant at recorded time."""
    variants = time_range.strategy_asc_boundaries(CASEY, 1)  # ±1 min
    assert len(variants) == 1
    assert variants[0]["minutes_offset"] == 0


# ---- scan_window --------------------------------------------------------

def test_scan_window_reports_min_recorded_max_and_boundary_count():
    scan = time_range.scan_window(CASEY)
    assert scan["hysteresis_minutes"] == 60
    assert scan["recorded_time"] == "18:00"
    assert scan["asc_at_min"]["sign"] == "Sagittarius"
    assert scan["asc_at_max"]["sign"] == "Capricorn"
    assert scan["sign_boundaries_in_window"] == 1
    assert "asc-boundaries" in scan["recommendation"]


def test_scan_window_returns_noop_for_zero_hysteresis():
    scan = time_range.scan_window(ALEX)
    assert scan["hysteresis_minutes"] == 0
    assert "not applicable" in scan["recommendation"]


# ---- routing layer ------------------------------------------------------

def test_resolve_output_path_with_time_range_routing(isolated_db, tmp_path):
    """Bare filename with --time-range-pair/--label routes under time-range/."""
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    out = render_docx.resolve_output_path(
        "syn-alex-casey.pdf",
        kind="synastry",
        cohort="lumina",
        time_range_pair="alex+casey",
        time_range_label="casey-1700",
    )
    assert out == target / "cohorts" / "lumina" / "time-range" / "alex+casey" / "casey-1700" / "syn-alex-casey.pdf"


def test_time_range_routing_skips_kind_subfolder(isolated_db, tmp_path):
    """When time-range is active, the kind subfolder is NOT prepended."""
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("default_output_subfolders", {"synastry": "synastry"})
    out = render_docx.resolve_output_path(
        "syn-alex-casey.pdf",
        kind="synastry",
        cohort="lumina",
        time_range_pair="alex+casey",
        time_range_label="casey-1700",
    )
    # Path should NOT contain a 'synastry' subfolder — time-range groups all kinds together.
    assert "/synastry/" not in str(out).replace("\\", "/")
    assert "/time-range/" in str(out).replace("\\", "/")


def test_time_range_routing_requires_both_pair_and_label(isolated_db, tmp_path):
    """Passing only one half falls back to kind routing."""
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("default_output_subfolders", {"synastry": "synastry"})
    out_pair_only = render_docx.resolve_output_path(
        "syn-alex-casey.pdf",
        kind="synastry", cohort="lumina",
        time_range_pair="alex+casey",
        time_range_label=None,
    )
    assert "/time-range/" not in str(out_pair_only).replace("\\", "/")
    assert "/synastry/" in str(out_pair_only).replace("\\", "/")


def test_time_range_routing_works_without_cohort(isolated_db, tmp_path):
    """time-range routing degrades cleanly when no cohort is set."""
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    out = render_docx.resolve_output_path(
        "syn-alex-casey.pdf",
        kind="synastry",
        time_range_pair="alex+casey",
        time_range_label="casey-1700",
    )
    assert out == target / "time-range" / "alex+casey" / "casey-1700" / "syn-alex-casey.pdf"


def test_time_range_routing_bypassed_by_explicit_subdir(isolated_db, tmp_path):
    """Explicit subdir in --output still bypasses all routing layers."""
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    out = render_docx.resolve_output_path(
        "custom/syn-alex-casey.pdf",
        kind="synastry", cohort="lumina",
        time_range_pair="alex+casey", time_range_label="casey-1700",
    )
    assert "/time-range/" not in str(out).replace("\\", "/")
    assert "/cohorts/" not in str(out).replace("\\", "/")
