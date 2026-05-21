"""J2000 Keplerian orbital elements for bodies that may lack Swiss Eph files.

Per spec §8: when seas_*.se1 / asteroid files are unavailable, fall back to
these elements + lib/kepler.py.

**Accuracy:** ±arcminutes for Ceres / Pallas / Juno / Vesta / Eris over
1800–2100. Chiron is heavily perturbed by Saturn and a single Keplerian
element set cannot do better than ~1–2 degree accuracy over the same range.
For arcminute Chiron precision, install `seas_18.se1` from astro.com and
Swiss Ephemeris will be used in preference to this fallback.

Angles in degrees, semi-major axis (a) in AU, period (P) in tropical years.
M0 is mean anomaly at the epoch.

**Note on Chiron M0:** Spec §8 lists M0 = 76.485° for Chiron at J2000.
Verification against PyEphem (independent Kepler solver) and JPL Small-Body
Database confirms the standard JPL J2000 value is M0 ≈ 348.062°. The spec's
value placed Chiron in late Aries / early Taurus in the 1960s, ~50° from
real Chiron's position in late Aquarius / early Pisces. This module uses
the JPL value; the spec is queued for revision. See
evals/reference-charts.json for the validated reference positions.
"""
from __future__ import annotations

# J2000 = 2000-01-01.5 TT = JD 2451545.0
J2000 = 2451545.0
# Eris elements use a more recent epoch (closer to perihelion) for better accuracy.
ERIS_EPOCH = 2459800.5  # 2022-07-30


ELEMENTS = {
    "Ceres": {
        "a": 2.7691651, "e": 0.0760091, "i": 10.59407,
        "Omega": 80.30553, "omega": 73.59770, "M0": 95.98905,
        "P_years": 4.6041, "epoch": J2000,
    },
    "Pallas": {
        "a": 2.7728118, "e": 0.2299838, "i": 34.83727,
        "Omega": 173.08006, "omega": 310.20706, "M0": 78.21443,
        "P_years": 4.6125, "epoch": J2000,
    },
    "Juno": {
        "a": 2.6685271, "e": 0.2570425, "i": 12.99178,
        "Omega": 169.85318, "omega": 248.10160, "M0": 33.16410,
        "P_years": 4.3623, "epoch": J2000,
    },
    "Vesta": {
        "a": 2.3617858, "e": 0.0886211, "i": 7.14180,
        "Omega": 103.85093, "omega": 151.19853, "M0": 169.39812,
        "P_years": 3.6299, "epoch": J2000,
    },
    "Chiron": {
        # JPL J2000 standard values; spec's M0=76.485 is queued for correction.
        "a": 13.6796, "e": 0.38132, "i": 6.9255,
        "Omega": 209.3829, "omega": 339.5193, "M0": 348.062,
        "P_years": 50.76, "epoch": J2000,
    },
    "Eris": {
        "a": 67.78290, "e": 0.43607, "i": 44.19200,
        "Omega": 35.94975, "omega": 151.66135, "M0": 205.98961,
        "P_years": 558.04, "epoch": ERIS_EPOCH,
    },
}
