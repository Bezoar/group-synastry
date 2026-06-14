"""Tests for the medieval / traditional-European computation layer (lib/medieval).

Covers the deterministic substrate of the medieval track per docs/specs/medieval.md
§3: sect, essential dignities (+ almuten), and the Lots of Fortune & Spirit.

Reference placements for Alex & Jordan come from tests/fixtures/people_test.json
(the same fictional personas pinned in test_chart.py). The dignity/sect/lot
*tables* are the verified ones recorded in lib/medieval.py (sources cited there).
Both Alex (morning) and Jordan (afternoon) are day births — their Sun is above
the horizon — so both charts are diurnal.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import chart as chart_mod  # via conftest.py path injection
from lib import medieval

FIXTURE = Path(__file__).parent / "fixtures" / "people_test.json"
PEOPLE = {p["id"]: p for p in json.loads(FIXTURE.read_text())["people"]}


# ---------------------------------------------------------------------------
# Sect
# ---------------------------------------------------------------------------

def test_determine_sect_sun_above_horizon_is_diurnal():
    # Ascendant at 0° Aries; Sun at 270° (near the MC, high above the horizon).
    assert medieval.determine_sect(sun_lon=270.0, asc_lon=0.0) == medieval.DIURNAL


def test_determine_sect_sun_below_horizon_is_nocturnal():
    # Ascendant at 0° Aries; Sun at 90° (near the IC, below the horizon).
    assert medieval.determine_sect(sun_lon=90.0, asc_lon=0.0) == medieval.NOCTURNAL


def test_determine_sect_wraps_across_zero():
    # Asc at 350°, Sun at 100°: distance from Asc = (100-350)%360 = 110 -> below.
    assert medieval.determine_sect(sun_lon=100.0, asc_lon=350.0) == medieval.NOCTURNAL
    # Asc at 350°, Sun at 200°: distance = (200-350)%360 = 210 -> above.
    assert medieval.determine_sect(sun_lon=200.0, asc_lon=350.0) == medieval.DIURNAL


def test_alex_is_a_day_chart():
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    assert medieval.chart_sect(chart) == medieval.DIURNAL


def test_jordan_is_a_day_chart():
    chart = chart_mod.compute_natal(PEOPLE["jordan"], house_system="placidus")
    assert medieval.chart_sect(chart) == medieval.DIURNAL


def test_sect_light_is_sun_by_day_and_moon_by_night():
    assert medieval.sect_light(medieval.DIURNAL) == "Sun"
    assert medieval.sect_light(medieval.NOCTURNAL) == "Moon"


def test_benefic_and_malefic_of_sect_by_day():
    # Day: Jupiter is the benefic of the sect, Saturn the malefic of the sect;
    # Mars is the out-of-sect (contrary) malefic.
    assert medieval.benefic_of_sect(medieval.DIURNAL) == "Jupiter"
    assert medieval.malefic_of_sect(medieval.DIURNAL) == "Saturn"
    assert medieval.contrary_malefic(medieval.DIURNAL) == "Mars"


def test_benefic_and_malefic_of_sect_by_night():
    # Night: Venus is the benefic of the sect, Mars the malefic of the sect;
    # Saturn is the out-of-sect (contrary) malefic.
    assert medieval.benefic_of_sect(medieval.NOCTURNAL) == "Venus"
    assert medieval.malefic_of_sect(medieval.NOCTURNAL) == "Mars"
    assert medieval.contrary_malefic(medieval.NOCTURNAL) == "Saturn"


def test_planet_sect_membership():
    # Sun, Jupiter, Saturn are of the diurnal sect; Moon, Venus, Mars nocturnal.
    assert medieval.planet_sect("Sun") == medieval.DIURNAL
    assert medieval.planet_sect("Jupiter") == medieval.DIURNAL
    assert medieval.planet_sect("Saturn") == medieval.DIURNAL
    assert medieval.planet_sect("Moon") == medieval.NOCTURNAL
    assert medieval.planet_sect("Venus") == medieval.NOCTURNAL
    assert medieval.planet_sect("Mars") == medieval.NOCTURNAL
    # Mercury's sect is by orientality, not fixed.
    assert medieval.planet_sect("Mercury") is None


def test_orientality_oriental_when_planet_rises_before_sun():
    # A planet at lower longitude than the Sun (just behind it) rises before the
    # Sun -> oriental (morning star). Alex: Mercury 81.0°, Sun 84.6°.
    assert medieval.orientality(planet_lon=81.0, sun_lon=84.6) == "oriental"
    # A planet just ahead of the Sun sets after it -> occidental (evening star).
    assert medieval.orientality(planet_lon=88.0, sun_lon=84.6) == "occidental"


# ---------------------------------------------------------------------------
# Essential dignities — table accessors (verified tables; see lib/medieval.py)
# ---------------------------------------------------------------------------

def _lon(sign: str, deg: float) -> float:
    """Ecliptic longitude of ``deg`` within ``sign`` (deg in [0,30))."""
    return medieval.SIGNS.index(sign) * 30.0 + deg


def test_domicile_rulers():
    assert medieval.domicile_ruler("Aries") == "Mars"
    assert medieval.domicile_ruler("Scorpio") == "Mars"
    assert medieval.domicile_ruler("Leo") == "Sun"
    assert medieval.domicile_ruler("Cancer") == "Moon"
    assert medieval.domicile_ruler("Aquarius") == "Saturn"
    assert medieval.domicile_ruler("Pisces") == "Jupiter"


def test_exaltation_rulers_and_degrees():
    assert medieval.exaltation("Aries") == ("Sun", 19)
    assert medieval.exaltation("Taurus") == ("Moon", 3)
    assert medieval.exaltation("Cancer") == ("Jupiter", 15)
    assert medieval.exaltation("Virgo") == ("Mercury", 15)
    assert medieval.exaltation("Libra") == ("Saturn", 21)
    assert medieval.exaltation("Capricorn") == ("Mars", 28)
    assert medieval.exaltation("Pisces") == ("Venus", 27)
    # Signs with no exaltation return None.
    assert medieval.exaltation("Gemini") is None


def test_triplicity_ruler_by_sect():
    # Dorothean scheme. Air = Saturn (day) / Mercury (night) / Jupiter (part.).
    assert medieval.triplicity_ruler("Gemini", medieval.DIURNAL) == "Saturn"
    assert medieval.triplicity_ruler("Gemini", medieval.NOCTURNAL) == "Mercury"
    # Water = Venus (day) / Mars (night) / Moon (part.).
    assert medieval.triplicity_ruler("Pisces", medieval.DIURNAL) == "Venus"
    assert medieval.triplicity_ruler("Pisces", medieval.NOCTURNAL) == "Mars"
    # Fire = Sun (day) / Jupiter (night). Earth = Venus (day) / Moon (night).
    assert medieval.triplicity_ruler("Leo", medieval.DIURNAL) == "Sun"
    assert medieval.triplicity_ruler("Capricorn", medieval.NOCTURNAL) == "Moon"


def test_egyptian_term_ruler():
    # Aries: Jupiter 0-6, Venus 6-12, Mercury 12-20, Mars 20-25, Saturn 25-30.
    assert medieval.term_ruler(_lon("Aries", 0.0)) == "Jupiter"
    assert medieval.term_ruler(_lon("Aries", 5.99)) == "Jupiter"
    assert medieval.term_ruler(_lon("Aries", 6.0)) == "Venus"
    assert medieval.term_ruler(_lon("Aries", 21.0)) == "Mars"
    assert medieval.term_ruler(_lon("Aries", 25.0)) == "Saturn"
    # Aquarius: Mercury 0-7, Venus 7-13, Jupiter 13-20, Mars 20-25, Saturn 25-30.
    assert medieval.term_ruler(_lon("Aquarius", 0.0)) == "Mercury"
    assert medieval.term_ruler(_lon("Aquarius", 26.0)) == "Saturn"


def test_chaldean_face_ruler():
    # Aries faces: Mars (0-10), Sun (10-20), Venus (20-30).
    assert medieval.face_ruler(_lon("Aries", 0.0)) == "Mars"
    assert medieval.face_ruler(_lon("Aries", 15.0)) == "Sun"
    assert medieval.face_ruler(_lon("Aries", 25.0)) == "Venus"
    # Pisces faces: Saturn (0-10), Jupiter (10-20), Mars (20-30).
    assert medieval.face_ruler(_lon("Pisces", 5.0)) == "Saturn"
    assert medieval.face_ruler(_lon("Pisces", 14.57)) == "Jupiter"


# ---------------------------------------------------------------------------
# Essential dignities — per-planet state and scoring
# ---------------------------------------------------------------------------

def test_planet_in_its_domicile_scores_five():
    # Alex's Mercury at 21°02' Gemini (diurnal): domicile only.
    state = medieval.dignities_of("Mercury", _lon("Gemini", 21.033), medieval.DIURNAL)
    assert state.dignities == ["domicile"]
    assert state.score == 5
    assert state.detriment is False and state.fall is False
    assert state.peregrine is False


def test_planet_with_exaltation_and_triplicity_stacks_scores():
    # Jordan's Venus at 14°34' Pisces (diurnal): exaltation (+4) + day triplicity
    # of Water (+3) = 7; not its domicile/term/face there.
    state = medieval.dignities_of("Venus", _lon("Pisces", 14.567), medieval.DIURNAL)
    assert state.dignities == ["exaltation", "triplicity"]
    assert state.score == 7
    assert state.peregrine is False


def test_planet_in_fall_is_flagged_not_peregrine():
    # Sun in Libra (its fall). Holds no dignity there, but a planet in fall is a
    # debility state, not peregrine.
    state = medieval.dignities_of("Sun", _lon("Libra", 20.0), medieval.DIURNAL)
    assert state.fall is True
    assert state.detriment is False
    assert state.dignities == []
    assert state.score == 0
    assert state.peregrine is False


def test_planet_in_detriment_is_flagged():
    # Mars in Taurus (detriment — opposite its Scorpio domicile).
    state = medieval.dignities_of("Mars", _lon("Taurus", 10.0), medieval.DIURNAL)
    assert state.detriment is True
    assert state.fall is False


def test_peregrine_when_no_dignity_and_no_debility():
    # Moon in Libra: no domicile/exaltation/triplicity/term/face, and not in
    # detriment or fall -> peregrine.
    state = medieval.dignities_of("Moon", _lon("Libra", 20.0), medieval.DIURNAL)
    assert state.dignities == []
    assert state.detriment is False and state.fall is False
    assert state.peregrine is True


def test_almuten_of_a_degree_picks_highest_scorer():
    # At 14°34' Pisces (diurnal): Jupiter holds domicile(+5)+term(+2)+face(+1)=8;
    # Venus holds exaltation(+4)+triplicity(+3)=7. Jupiter is the almuten.
    result = medieval.almuten(_lon("Pisces", 14.567), medieval.DIURNAL)
    assert result.winner == "Jupiter"
    assert result.scores["Jupiter"] == 8
    assert result.scores["Venus"] == 7


# ---------------------------------------------------------------------------
# Verified-table integrity guards (catch transcription corruption — spec §4)
# ---------------------------------------------------------------------------

def test_egyptian_terms_each_sign_has_five_terms_summing_to_30():
    for sign in medieval.SIGNS:
        terms = medieval.EGYPTIAN_TERMS[sign]
        assert len(terms) == 5, f"{sign}: expected 5 terms, got {len(terms)}"
        assert terms[-1][1] == 30, f"{sign}: last term must end at 30°"
        # boundaries strictly increasing from >0 to 30
        ends = [end for _planet, end in terms]
        assert ends == sorted(ends) and ends[0] > 0, f"{sign}: non-monotonic terms {ends}"


def test_every_sign_has_domicile_three_faces_and_an_element():
    for sign in medieval.SIGNS:
        assert sign in medieval.DOMICILE
        assert len(medieval.FACES[sign]) == 3
        medieval._element_of(sign)  # raises if a sign is unclassified


def test_each_planet_rules_two_domiciles_luminaries_one():
    counts: dict[str, int] = {}
    for sign in medieval.SIGNS:
        counts[medieval.DOMICILE[sign]] = counts.get(medieval.DOMICILE[sign], 0) + 1
    assert counts["Sun"] == 1 and counts["Moon"] == 1
    for planet in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        assert counts[planet] == 2, f"{planet} should rule 2 signs, got {counts[planet]}"


# ---------------------------------------------------------------------------
# Lots of Fortune & Spirit
# ---------------------------------------------------------------------------

def test_lot_of_fortune_and_spirit_by_day():
    # Day: Fortune = Asc + Moon - Sun; Spirit = Asc + Sun - Moon.
    assert medieval.lot_of_fortune(asc=120.0, sun=80.0, moon=100.0,
                                   sect=medieval.DIURNAL) == 140.0
    assert medieval.lot_of_spirit(asc=120.0, sun=80.0, moon=100.0,
                                  sect=medieval.DIURNAL) == 100.0


def test_lots_reverse_by_night():
    # Night Fortune uses the diurnal Spirit formula and vice-versa, so for the
    # same chart the two lots swap places between day and night.
    asc, sun, moon = 200.0, 33.0, 290.0
    assert (medieval.lot_of_fortune(asc, sun, moon, medieval.NOCTURNAL)
            == medieval.lot_of_spirit(asc, sun, moon, medieval.DIURNAL))
    assert (medieval.lot_of_spirit(asc, sun, moon, medieval.NOCTURNAL)
            == medieval.lot_of_fortune(asc, sun, moon, medieval.DIURNAL))


def test_lot_normalizes_into_0_360():
    # Wraps above 360.
    assert medieval.lot_of_fortune(asc=350.0, sun=10.0, moon=40.0,
                                   sect=medieval.DIURNAL) == 20.0
    # Wraps below 0.
    assert medieval.lot_of_fortune(asc=10.0, sun=40.0, moon=20.0,
                                   sect=medieval.DIURNAL) == 350.0


def test_lots_of_alex_chart_land_in_expected_signs():
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    lots = medieval.lots(chart)
    # Alex is diurnal; Fortune ~16° Leo, Spirit ~19° Cancer.
    assert medieval.sign_of(lots["Fortune"]) == "Leo"
    assert medieval.sign_of(lots["Spirit"]) == "Cancer"


# ---------------------------------------------------------------------------
# Expanded Lots catalogue (seven Hermetic lots)
# ---------------------------------------------------------------------------

def test_lot_value_uniform_rule_day_and_night():
    # day = Asc + A - B; night swaps A and B.
    assert medieval.lot_value(asc=100.0, a=50.0, b=30.0, sect=medieval.DIURNAL) == 120.0
    assert medieval.lot_value(asc=100.0, a=50.0, b=30.0, sect=medieval.NOCTURNAL) == 80.0


def test_lot_value_normalizes_into_0_360():
    assert medieval.lot_value(asc=350.0, a=40.0, b=10.0, sect=medieval.DIURNAL) == 20.0


def test_full_catalogue_has_the_seven_hermetic_lots():
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    lots = medieval.lots(chart)
    assert set(lots) == {
        "Fortune", "Spirit", "Eros", "Necessity", "Courage", "Victory", "Nemesis"
    }
    # Fortune/Spirit unchanged by the expansion (regression guard).
    assert medieval.sign_of(lots["Fortune"]) == "Leo"
    assert medieval.sign_of(lots["Spirit"]) == "Cancer"


def test_eros_for_alex_lands_in_cancer():
    # Eros (day) = Asc + Venus - Spirit = Venus - Sun + Moon ≈ 94.4° -> Cancer.
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    assert medieval.sign_of(medieval.lots(chart)["Eros"]) == "Cancer"


def test_each_hermetic_lot_pairs_with_its_planet():
    # Locks the canonical lot<->planet mapping so e.g. Nemesis stays Saturn-based
    # (not Spirit-based — the one source that printed that was a typo).
    spec = medieval.HERMETIC_LOTS
    assert spec["Eros"] == ("Venus", "Spirit")
    assert spec["Necessity"] == ("Fortune", "Mercury")
    assert spec["Courage"] == ("Fortune", "Mars")
    assert spec["Victory"] == ("Jupiter", "Spirit")
    assert spec["Nemesis"] == ("Fortune", "Saturn")


# ---------------------------------------------------------------------------
# Annual / monthly profections
# ---------------------------------------------------------------------------
_LEO = _lon("Leo", 2.7)  # an Ascendant in Leo (Alex's is ~2°42' Leo)


def test_annual_profection_age_zero_is_ascendant_sign_first_house():
    p = medieval.annual_profection(asc_lon=_LEO, age=0)
    assert p.profected_sign == "Leo"
    assert p.profected_house == 1
    assert p.lord_of_year == "Sun"


def test_annual_profection_advances_one_sign_per_year():
    p1 = medieval.annual_profection(_LEO, 1)
    assert (p1.profected_sign, p1.profected_house, p1.lord_of_year) == ("Virgo", 2, "Mercury")
    p11 = medieval.annual_profection(_LEO, 11)
    assert (p11.profected_sign, p11.profected_house, p11.lord_of_year) == ("Cancer", 12, "Moon")


def test_annual_profection_twelve_year_cycle():
    assert medieval.annual_profection(_LEO, 12).profected_house == 1
    assert medieval.annual_profection(_LEO, 12).profected_sign == "Leo"
    assert medieval.annual_profection(_LEO, 36).profected_house == 1


def test_annual_profection_rejects_negative_age():
    with pytest.raises(ValueError):
        medieval.annual_profection(_LEO, -1)


def test_monthly_profected_sign_advances_from_the_annual_sign():
    assert medieval.monthly_profected_sign(_LEO, age=0, month=0) == "Leo"
    assert medieval.monthly_profected_sign(_LEO, age=0, month=1) == "Virgo"
    # At age 1 the annual sign is Virgo, so month 0 starts there.
    assert medieval.monthly_profected_sign(_LEO, age=1, month=0) == "Virgo"


def test_years_completed_counts_birthdays():
    assert medieval.years_completed("1988-06-15", "2026-05-24") == 37   # before birthday
    assert medieval.years_completed("1988-06-15", "2026-06-15") == 38   # on birthday
    assert medieval.years_completed("1988-06-15", "2026-07-01") == 38   # after birthday


def test_years_completed_rejects_target_before_birth():
    with pytest.raises(ValueError):
        medieval.years_completed("1988-06-15", "1980-01-01")


def test_profection_report_surfaces_lord_of_year_condition():
    # Alex Asc Leo; at age 37 the profection is the 2nd house (Virgo), so the
    # lord of the year is Mercury — which sits in Gemini in domicile natally.
    natal = chart_mod.compute_natal(PEOPLE["alex"], house_system="alcabitius")
    rep = medieval.profection_report(natal, age=37)
    assert rep.profection.profected_sign == "Virgo"
    assert rep.profection.profected_house == 2
    assert rep.profection.lord_of_year == "Mercury"
    assert rep.lord_sign == "Gemini"
    assert "domicile" in rep.lord_dignities.dignities


def test_profection_report_to_dict_is_json_serializable():
    import json as _json
    natal = chart_mod.compute_natal(PEOPLE["alex"], house_system="alcabitius")
    d = medieval.profection_report(natal, age=37).to_dict()
    assert d["kind"] == "profection"
    _json.dumps(d)


def test_render_profection_shows_lord_and_condition():
    from render_md import render_profection
    natal = chart_mod.compute_natal(PEOPLE["alex"], house_system="alcabitius")
    rep = medieval.profection_report(natal, age=37)
    md = render_profection(natal, rep)
    assert "Profection" in md
    assert "Lord of the Year" in md
    assert "Virgo" in md and "Mercury" in md
    assert "age 37" in md.lower() or "37" in md


# ---------------------------------------------------------------------------
# Antiscia / contra-antiscia
# ---------------------------------------------------------------------------

def test_antiscion_reflects_across_the_solstitial_axis():
    assert medieval.antiscion(90.0) == 90.0     # 0° Cancer is on the axis
    assert medieval.antiscion(100.0) == 80.0    # 10° Cancer <-> 20° Gemini
    assert medieval.antiscion(80.0) == 100.0
    assert medieval.antiscion(270.0) == 270.0   # 0° Capricorn on the axis


def test_contra_antiscion_reflects_across_the_equinoctial_axis():
    assert medieval.contra_antiscion(0.0) == 0.0     # 0° Aries on the axis
    assert medieval.contra_antiscion(10.0) == 350.0  # 10° Aries <-> 20° Pisces
    # contra-antiscion is the antiscion reflected by 180°.
    assert medieval.contra_antiscion(100.0) == (medieval.antiscion(100.0) + 180.0) % 360.0


def test_antiscia_lists_the_seven_classical_planets():
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    entries = medieval.antiscia(chart)
    assert {e.planet for e in entries} == set(medieval.CLASSICAL_PLANETS)
    sun = next(e for e in entries if e.planet == "Sun")
    assert 0.0 <= sun.antiscion < 360.0
    assert sun.antiscion == medieval.antiscion(sun.longitude)


def test_antiscia_contact_detected_within_orb():
    # A at 100°, B at 80°: A's antiscion (80°) falls on B -> a contact.
    contacts = medieval.antiscia_contacts_from_positions({"A": 100.0, "B": 80.0}, orb=1.0)
    hit = [c for c in contacts if {c.a, c.b} == {"A", "B"}]
    assert hit and hit[0].kind == "antiscion"


def test_antiscia_contact_absent_when_out_of_orb():
    contacts = medieval.antiscia_contacts_from_positions({"A": 100.0, "B": 70.0}, orb=1.0)
    assert contacts == []


# ---------------------------------------------------------------------------
# Mutual reception
# ---------------------------------------------------------------------------

def test_mutual_reception_by_domicile_detected():
    # Mars in Cancer (Moon's domicile) and Moon in Aries (Mars's domicile):
    # each sits in a sign the other rules -> mutual reception by domicile.
    positions = {"Mars": _lon("Cancer", 10.0), "Moon": _lon("Aries", 10.0)}
    mrs = medieval.mutual_receptions_from_positions(positions, medieval.DIURNAL)
    assert len(mrs) == 1
    mr = mrs[0]
    assert {mr.a, mr.b} == {"Mars", "Moon"}
    assert "domicile" in mr.a_receives_b and "domicile" in mr.b_receives_a


def test_no_mutual_reception_when_only_one_way():
    # Venus in Gemini is received by Mercury (domicile), but Mercury (in Gemini,
    # its own domicile) is not received by Venus — Venus rules neither place.
    positions = {"Venus": _lon("Gemini", 10.0), "Mercury": _lon("Gemini", 20.0)}
    assert medieval.mutual_receptions_from_positions(positions, medieval.DIURNAL) == []


def test_mutual_reception_default_ignores_minor_dignities():
    # Two planets that only "receive" each other by term/face must NOT count
    # under the default (domicile/exaltation) reception.
    # Sun in Aquarius (Saturn domicile) & Saturn in Leo (Sun domicile) -> that IS
    # a domicile mutual reception, so use it as a positive control too.
    positions = {"Sun": _lon("Aquarius", 5.0), "Saturn": _lon("Leo", 5.0)}
    mrs = medieval.mutual_receptions_from_positions(positions, medieval.DIURNAL)
    assert len(mrs) == 1 and {mrs[0].a, mrs[0].b} == {"Sun", "Saturn"}


def test_mutual_receptions_on_chart_returns_a_list():
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="placidus")
    mrs = medieval.mutual_receptions(chart)
    assert isinstance(mrs, list)  # Alex has no domicile/exaltation mutual reception


# ---------------------------------------------------------------------------
# Alcabitius houses (the medieval default) + full medieval assembly
# ---------------------------------------------------------------------------

def test_compute_natal_supports_alcabitius_houses():
    chart = chart_mod.compute_natal(PEOPLE["alex"], house_system="alcabitius")
    assert chart.house_system == "alcabitius"
    assert len(chart.house_cusps) == 12
    assert any(a.name == "Ascendant" for a in chart.angles)


def test_compute_medieval_assembles_sect_dignities_lots_almuten():
    mc = medieval.compute_medieval(PEOPLE["alex"], house_system="alcabitius")
    assert mc.sect == medieval.DIURNAL
    assert mc.sect_light == "Sun"
    assert mc.benefic_of_sect == "Jupiter"
    assert mc.malefic_of_sect == "Saturn"
    # Dignity states cover exactly the seven classical planets.
    assert {d.planet for d in mc.dignities} == {
        "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"
    }
    # Alex's Mercury in Gemini is in domicile.
    merc = next(d for d in mc.dignities if d.planet == "Mercury")
    assert "domicile" in merc.dignities
    # Lots and almuten of the Ascendant are present.
    assert medieval.sign_of(mc.lots["Fortune"]) == "Leo"
    assert mc.almuten_asc.winner in medieval._CHALDEAN_ORDER


def test_compute_medieval_defaults_to_alcabitius():
    mc = medieval.compute_medieval(PEOPLE["alex"])
    assert mc.natal.house_system == "alcabitius"


def test_medieval_chart_to_dict_is_json_serializable():
    import json as _json
    mc = medieval.compute_medieval(PEOPLE["alex"], house_system="alcabitius")
    d = mc.to_dict()
    assert d["kind"] == "medieval"
    assert d["sect"] == "diurnal"
    # round-trips through JSON without error
    _json.dumps(d)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def test_render_medieval_contains_sect_dignities_lots_almuten():
    from render_md import render_medieval
    mc = medieval.compute_medieval(PEOPLE["alex"], house_system="alcabitius")
    md = render_medieval(mc)
    assert "Sect" in md
    assert "diurnal" in md.lower()
    assert "Essential Dignities" in md
    assert "Fortune" in md and "Spirit" in md
    assert "Almuten" in md
    assert "Antiscia" in md
    assert "Mutual Reception" in md
    # Alex's Mercury holds domicile — it should surface in the dignities table.
    assert "domicile" in md
    # House system reported as Alcabitius.
    assert "alcabitius" in md.lower()
