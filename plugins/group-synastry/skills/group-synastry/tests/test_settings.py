"""Tests for the settings.json persistence layer (eval 18)."""
from __future__ import annotations

import json

import pytest

from lib import settings, env  # via conftest path injection


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Redirect settings.json into a tmp dir for the duration of one test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # env.data_dir() / settings_json_path() read XDG_CONFIG_HOME at call time,
    # so no further patching is needed unless we're on Claude.ai. Guard against
    # that by also forcing the non-Claude.ai branch:
    monkeypatch.setattr(env, "is_claude_ai", lambda: False)
    yield tmp_path / "group-synastry" / "settings.json"


def test_load_returns_skeleton_when_missing(isolated_settings):
    data = settings.load()
    assert data == {"version": settings.SCHEMA_VERSION}
    assert not isolated_settings.exists()


def test_set_and_get_roundtrip(isolated_settings):
    settings.set_pref("default_house_system", "whole-sign")
    assert isolated_settings.exists()
    assert settings.get("default_house_system") == "whole-sign"
    on_disk = json.loads(isolated_settings.read_text())
    assert on_disk["default_house_system"] == "whole-sign"
    assert on_disk["version"] == settings.SCHEMA_VERSION
    assert "updated_at" in on_disk


def test_default_house_system_falls_back_when_unset(isolated_settings):
    assert settings.default_house_system() == "placidus"
    settings.set_pref("default_house_system", "koch")
    assert settings.default_house_system() == "koch"


def test_set_pref_rejects_unknown_key(isolated_settings):
    with pytest.raises(ValueError, match="Unknown setting"):
        settings.set_pref("favorite_color", "ultraviolet")


def test_clear_removes_key(isolated_settings):
    settings.set_pref("default_house_system", "whole-sign")
    settings.clear("default_house_system")
    assert settings.get("default_house_system") is None
    assert settings.default_house_system() == "placidus"


def test_unknown_keys_round_trip_through_save(isolated_settings):
    """A future-version key should survive a load/save cycle untouched."""
    isolated_settings.parent.mkdir(parents=True, exist_ok=True)
    isolated_settings.write_text(json.dumps({
        "version": 1,
        "default_house_system": "whole-sign",
        "default_lunar_method": "siderial-mean-node",  # hypothetical future key
    }))
    settings.set_pref("default_house_system", "koch")
    on_disk = json.loads(isolated_settings.read_text())
    assert on_disk["default_lunar_method"] == "siderial-mean-node"


def test_chart_cli_consults_settings(isolated_settings, monkeypatch, capsys):
    """End-to-end: setting default_house_system changes chart.py's default."""
    import chart

    captured = {}

    def fake_compute_natal(person, house_system="placidus"):
        captured["house_system"] = house_system
        return chart.NatalChart(
            person_id=person.get("id", "x"),
            display_name=person.get("display_name", "x"),
            birth=person.get("birth", {}),
            julian_day_ut=0.0,
            ut_iso="2000-01-01T00:00:00Z",
            house_system=house_system,
        )

    def fake_load():
        return {"version": 1, "people": [{"id": "alex", "display_name": "Alex"}]}

    monkeypatch.setattr(chart, "compute_natal", fake_compute_natal)
    monkeypatch.setattr(chart.db, "load", fake_load)

    settings.set_pref("default_house_system", "whole-sign")
    rc = chart._main(["natal", "alex", "--json"])
    assert rc == 0
    assert captured["house_system"] == "whole-sign"

    # Explicit --house-system on the command line wins over the saved default.
    captured.clear()
    rc = chart._main(["natal", "alex", "--house-system", "koch", "--json"])
    assert rc == 0
    assert captured["house_system"] == "koch"


def test_default_output_dir_is_known_key(isolated_settings):
    settings.set_pref("default_output_dir", "/tmp/some/charts")
    assert settings.get("default_output_dir") == "/tmp/some/charts"


def test_outputs_dir_uses_default_output_dir_when_set(isolated_settings, tmp_path):
    target = tmp_path / "proton" / "charts"
    settings.set_pref("default_output_dir", str(target))
    resolved = env.outputs_dir()
    assert resolved == target, f"outputs_dir() should return the configured path, got {resolved}"
    assert target.exists(), "outputs_dir() should create the configured directory"


def test_outputs_dir_falls_back_to_cwd_when_unset(isolated_settings, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # No default_output_dir set; should return cwd (not the configured path).
    assert env.outputs_dir() == tmp_path


def test_resolve_output_path_relative_uses_outputs_dir(isolated_settings, tmp_path):
    import render_docx
    target = tmp_path / "proton-charts"
    settings.set_pref("default_output_dir", str(target))
    resolved = render_docx.resolve_output_path("foo.pdf")
    assert resolved == target / "foo.pdf"


def test_resolve_output_path_absolute_is_honored(isolated_settings, tmp_path):
    import render_docx
    settings.set_pref("default_output_dir", str(tmp_path / "should-be-ignored"))
    abs_path = "/tmp/specific/location.pdf"
    assert str(render_docx.resolve_output_path(abs_path)) == abs_path


# ---- default_output_subfolders (kind-based routing) ---------------------

def test_subfolder_for_kind_returns_none_when_unset(isolated_settings):
    assert settings.subfolder_for_kind("natal") is None
    assert settings.subfolder_for_kind("synastry") is None


def test_subfolder_for_kind_returns_configured_value(isolated_settings):
    settings.set_pref("default_output_subfolders", {
        "natal": "birth-charts",
        "synastry": "synastry",
        "composite": "synastry",
    })
    assert settings.subfolder_for_kind("natal") == "birth-charts"
    assert settings.subfolder_for_kind("synastry") == "synastry"
    assert settings.subfolder_for_kind("composite") == "synastry"
    assert settings.subfolder_for_kind("davison") is None


def test_subfolder_for_kind_strips_leading_slashes(isolated_settings):
    settings.set_pref("default_output_subfolders", {"natal": "/birth-charts/"})
    assert settings.subfolder_for_kind("natal") == "birth-charts"


def test_resolve_output_path_routes_bare_filename_to_kind_subfolder(
    isolated_settings, tmp_path
):
    import render_docx
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("default_output_subfolders", {
        "natal": "birth-charts",
        "synastry": "synastry",
        "composite": "synastry",
    })
    assert render_docx.resolve_output_path("alex.pdf", kind="natal") == \
        target / "birth-charts" / "alex.pdf"
    assert render_docx.resolve_output_path("alex-jordan.pdf", kind="synastry") == \
        target / "synastry" / "alex-jordan.pdf"
    assert render_docx.resolve_output_path("alex-jordan.pdf", kind="composite") == \
        target / "synastry" / "alex-jordan.pdf"


def test_resolve_output_path_explicit_subdir_bypasses_routing(
    isolated_settings, tmp_path
):
    """If the user puts a slash in --output, honor that exactly — don't double-route."""
    import render_docx
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("default_output_subfolders", {"natal": "birth-charts"})
    assert render_docx.resolve_output_path("custom/alex.pdf", kind="natal") == \
        target / "custom" / "alex.pdf"


def test_resolve_output_path_no_routing_when_kind_unset(isolated_settings, tmp_path):
    """Routing only applies when kind is passed AND a mapping exists."""
    import render_docx
    target = tmp_path / "out"
    settings.set_pref("default_output_dir", str(target))
    settings.set_pref("default_output_subfolders", {"natal": "birth-charts"})
    assert render_docx.resolve_output_path("alex.pdf") == target / "alex.pdf"
    assert render_docx.resolve_output_path("alex.pdf", kind="davison") == \
        target / "alex.pdf"


def test_resolve_output_path_absolute_bypasses_subfolder_routing(
    isolated_settings, tmp_path
):
    """Absolute --output is the escape hatch — never gets remapped."""
    import render_docx
    settings.set_pref("default_output_subfolders", {"natal": "birth-charts"})
    abs_path = str(tmp_path / "specific" / "alex.pdf")
    assert str(render_docx.resolve_output_path(abs_path, kind="natal")) == abs_path
