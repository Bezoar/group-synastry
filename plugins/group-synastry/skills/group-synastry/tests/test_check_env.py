"""Tests for the dependency doctor (scripts/check_env.py)."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import check_env  # via conftest.py path injection


def test_gather_covers_expected_items_and_tiers():
    checks = {c["key"]: c for c in check_env.gather()}
    assert {"python", "pyswisseph", "node", "node_modules", "soffice", "seas_18"} <= set(checks)
    assert checks["python"]["tier"] == "core"
    assert checks["pyswisseph"]["tier"] == "core"
    assert checks["node"]["tier"] == "optional"
    assert checks["node_modules"]["tier"] == "optional"
    assert checks["soffice"]["tier"] == "optional"
    assert checks["seas_18"]["tier"] == "info"


def test_core_satisfied_when_pyswisseph_present():
    # pyswisseph is a test dependency, so core must be satisfied here.
    checks = check_env.gather()
    assert check_env.core_satisfied(checks) is True
    assert check_env._main([]) == 0


def test_core_missing_when_pyswisseph_absent(monkeypatch):
    real_find = importlib.util.find_spec

    def fake_find(name, *args, **kwargs):
        if name == "swisseph":
            return None
        return real_find(name, *args, **kwargs)

    monkeypatch.setattr(check_env.importlib.util, "find_spec", fake_find)
    checks = {c["key"]: c for c in check_env.gather()}
    swe = checks["pyswisseph"]
    assert swe["ok"] is False
    assert swe["fix"] and "pip install" in swe["fix"]
    assert check_env.core_satisfied(list(checks.values())) is False
    # Exit code signals the missing core dep.
    assert check_env._main([]) == 1


def test_optional_misses_do_not_block_core(monkeypatch):
    monkeypatch.setattr(check_env.shutil, "which", lambda name: None)
    monkeypatch.setattr(check_env, "_locate_soffice", lambda: None)
    monkeypatch.setattr(check_env, "NODE_MODULES", Path("/nonexistent/node_modules"))
    checks = {c["key"]: c for c in check_env.gather()}

    assert checks["node"]["ok"] is False and checks["node"]["fix"]
    assert checks["node_modules"]["ok"] is False
    assert "npm install" in checks["node_modules"]["fix"]
    assert checks["soffice"]["ok"] is False and checks["soffice"]["fix"]

    # Optional gaps must NOT flip core satisfaction (pyswisseph still present).
    assert check_env.core_satisfied(list(checks.values())) is True


def test_human_output_has_parseable_summary():
    text = check_env.render_human(check_env.gather())
    summary = [ln for ln in text.splitlines() if ln.startswith("SUMMARY ")]
    assert summary, "missing SUMMARY line"
    assert "core_ok=true" in summary[0]
    assert "pyswisseph=ok" in summary[0]


def test_json_output_shape(capsys):
    rc = check_env._main(["--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["core_satisfied"] is True
    assert isinstance(data["checks"], list) and data["checks"]
    assert {"key", "tier", "ok", "fix"} <= set(data["checks"][0])


def test_pip_command_targets_requirements_file():
    cmd = check_env._pip_install_cmd()
    assert "pip install -r" in cmd
    assert "requirements.txt" in cmd
