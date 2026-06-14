"""Unit tests for the shared formatting helpers extracted during the
pre-merge DRY-up (sign_of, shorter_arc_separation)."""
from __future__ import annotations

from lib import formatting


def test_sign_of_basic_and_wrapping():
    assert formatting.sign_of(0.0) == "Aries"
    assert formatting.sign_of(95.0) == "Cancer"
    assert formatting.sign_of(359.9) == "Pisces"
    assert formatting.sign_of(360.0) == "Aries"   # wraps
    assert formatting.sign_of(-1.0) == "Pisces"   # negative normalizes


def test_shorter_arc_separation():
    assert formatting.shorter_arc_separation(10.0, 20.0) == 10.0
    assert formatting.shorter_arc_separation(350.0, 10.0) == 20.0   # across 0°
    assert formatting.shorter_arc_separation(0.0, 180.0) == 180.0
    assert formatting.shorter_arc_separation(0.0, 190.0) == 170.0   # takes shorter side
    assert formatting.shorter_arc_separation(123.4, 123.4) == 0.0
