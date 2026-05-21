"""Keplerian fallback for bodies whose Swiss Eph files aren't installed.

Solves Kepler's equation, computes heliocentric coordinates, transforms to
geocentric ecliptic longitude. Earth's heliocentric position is queried from
Swiss Ephemeris (which always works for Earth via its built-in algorithms or
Moshier fallback).
"""
from __future__ import annotations

import math
from typing import Optional

import swisseph as swe

from . import orbital_elements as oe


_TWO_PI = 2.0 * math.pi
_DEG = math.pi / 180.0
_OBLIQUITY_J2000_DEG = 23.4392911  # mean obliquity at J2000 — good enough for ecliptic-frame work


def _solve_kepler(M_rad: float, e: float, tol: float = 1e-10, max_iter: int = 50) -> float:
    """Solve M = E - e sin E for E (eccentric anomaly), Newton-Raphson."""
    M_rad = ((M_rad + math.pi) % _TWO_PI) - math.pi
    # Good starting guess
    E = M_rad if e < 0.8 else math.pi
    for _ in range(max_iter):
        f = E - e * math.sin(E) - M_rad
        fp = 1.0 - e * math.cos(E)
        dE = -f / fp
        E += dE
        if abs(dE) < tol:
            break
    return E


def heliocentric_xyz(name: str, jd_ut: float):
    """Return heliocentric ecliptic-of-date (x, y, z) in AU for a Keplerian body.

    Uses J2000 ecliptic frame; for arcminute-grade asteroid astrology this is
    sufficient over 1800-2100 (precession of ecliptic ≈ 0.014°/century).
    """
    el = oe.ELEMENTS[name]
    P_days = el["P_years"] * 365.25
    n = _TWO_PI / P_days  # mean motion (rad/day)
    M = (el["M0"] * _DEG) + n * (jd_ut - el["epoch"])
    E = _solve_kepler(M, el["e"])
    # True anomaly
    cos_E = math.cos(E)
    sin_E = math.sin(E)
    one_minus_e2 = math.sqrt(1.0 - el["e"] ** 2)
    nu = math.atan2(one_minus_e2 * sin_E, cos_E - el["e"])
    r = el["a"] * (1.0 - el["e"] * cos_E)
    # Heliocentric in orbital plane: x' along periapsis
    xp = r * math.cos(nu)
    yp = r * math.sin(nu)
    # Rotate by ω (arg perihelion), then incline by i, then rotate by Ω (long asc node)
    om = el["omega"] * _DEG
    inc = el["i"] * _DEG
    Om = el["Omega"] * _DEG
    cos_om, sin_om = math.cos(om), math.sin(om)
    cos_i, sin_i = math.cos(inc), math.sin(inc)
    cos_Om, sin_Om = math.cos(Om), math.sin(Om)
    x1 = cos_om * xp - sin_om * yp
    y1 = sin_om * xp + cos_om * yp
    z1 = 0.0
    # incline around x1
    x2 = x1
    y2 = cos_i * y1
    z2 = sin_i * y1
    # rotate around z by Ω
    x = cos_Om * x2 - sin_Om * y2
    y = sin_Om * x2 + cos_Om * y2
    z = z2
    return x, y, z


def _earth_heliocentric_xyz(jd_ut: float):
    """Earth's heliocentric ecliptic-of-J2000 (x, y, z) in AU via Swiss Eph."""
    # Use Moshier fallback so this works without ephemeris files.
    flags = swe.FLG_MOSEPH | swe.FLG_HELCTR | swe.FLG_J2000 | swe.FLG_XYZ
    pos, _ = swe.calc_ut(jd_ut, swe.EARTH, flags)
    return pos[0], pos[1], pos[2]


def geocentric_longitude(name: str, jd_ut: float) -> float:
    """Return apparent geocentric ecliptic longitude (degrees, 0-360)."""
    hx, hy, hz = heliocentric_xyz(name, jd_ut)
    ex, ey, ez = _earth_heliocentric_xyz(jd_ut)
    gx, gy, gz = hx - ex, hy - ey, hz - ez
    lon = math.degrees(math.atan2(gy, gx)) % 360.0
    return lon
