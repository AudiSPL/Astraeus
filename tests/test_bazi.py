"""BaZi engine tests.

The day-pillar anchor is the one value here that came from calibration rather
than derivation, so it is checked against three independent dates. If those
three hold, the continuous sexagenary count is right for every other date.
"""

from __future__ import annotations

import pytest

from app.core.bazi import (
    BRANCHES,
    DAY_CYCLE_OFFSET,
    STEMS,
    BaziConfig,
    _cycle_index,
    _solar_term_jd,
    _jd_to_iso,
    compute_bazi,
)

REFERENCE = dict(date="1984-07-24", time="05:10:00",
                 timezone_name="Europe/Belgrade", longitude=20.46513)


@pytest.fixture(scope="module")
def chart():
    return compute_bazi(**REFERENCE, config=BaziConfig(gender="male"))


# --- day-pillar calibration ------------------------------------------------

@pytest.mark.parametrize("y, m, d, expected", [
    (1949, 10, 1, "Jia Zi"),    # founding of the PRC, widely recorded as Jia Zi
    (1900, 1, 1, "Jia Xu"),
    (2000, 1, 1, "Wu Wu"),
])
def test_day_cycle_anchor(y, m, d, expected):
    import swisseph as swe
    idx = (int(swe.julday(y, m, d, 12.0)) + DAY_CYCLE_OFFSET) % 60
    assert f"{STEMS[idx % 10]} {BRANCHES[idx % 12]}" == expected


def test_day_cycle_advances_by_one_per_day_and_repeats_every_sixty():
    import swisseph as swe

    def idx(y, m, d):
        return (int(swe.julday(y, m, d, 12.0)) + DAY_CYCLE_OFFSET) % 60

    assert (idx(1984, 7, 25) - idx(1984, 7, 24)) % 60 == 1
    assert idx(1984, 7, 24) == idx(1984, 9, 22)


def test_cycle_index_rejects_impossible_pairs():
    """Only 60 of the 120 stem/branch pairs exist: parity must match."""
    assert _cycle_index(0, 0) == 0            # Jia Zi
    with pytest.raises(ValueError):
        _cycle_index(0, 1)                     # Jia Chou cannot occur


# --- solar terms -----------------------------------------------------------

@pytest.mark.parametrize("deg, year, month, day_range", [
    (315, 1984, 2, (3, 5)),    # Li Chun
    (105, 1984, 7, (6, 8)),    # Xiao Shu
    (135, 1984, 8, (7, 9)),    # Li Qiu
    (255, 1984, 12, (6, 8)),   # Da Xue
])
def test_solar_terms_land_on_their_conventional_dates(deg, year, month, day_range):
    import swisseph as swe
    iso = _jd_to_iso(_solar_term_jd(deg, swe.julday(year, month, 5, 12.0)))
    assert iso[:7] == f"{year}-{month:02d}"
    assert day_range[0] <= int(iso[8:10]) <= day_range[1]


# --- the reference chart ---------------------------------------------------

def test_four_pillars(chart):
    got = {p["pillar"]: p["combined"]["name"] for p in chart["four_pillars"]}
    assert got == {"year": "Jia Zi", "month": "Xin Wei",
                   "day": "Ji Wei", "hour": "Bing Yin"}


def test_year_uses_li_chun_not_january(chart):
    assert chart["bazi_year"] == 1984
    assert chart["li_chun_utc"].startswith("1984-02-04")


def test_a_january_birth_belongs_to_the_previous_bazi_year():
    """The whole point of the Li Chun boundary.

    A Gregorian-year approximation would call this 1985; BaZi calls it 1984,
    because Li Chun 1985 had not happened yet.
    """
    early = compute_bazi("1985-01-20", "12:00:00", "Europe/Belgrade", 20.46513)
    assert early["bazi_year"] == 1984
    assert early["four_pillars"][0]["combined"]["name"] == "Jia Zi"

    late = compute_bazi("1985-02-10", "12:00:00", "Europe/Belgrade", 20.46513)
    assert late["bazi_year"] == 1985
    assert late["four_pillars"][0]["combined"]["name"] == "Yi Chou"


def test_month_uses_solar_terms_not_calendar_months():
    """Two births in the same Gregorian month, different BaZi months."""
    before = compute_bazi("1984-07-02", "12:00:00", "Europe/Belgrade", 20.46513)
    after = compute_bazi("1984-07-24", "12:00:00", "Europe/Belgrade", 20.46513)
    assert before["four_pillars"][1]["branch"]["name"] == "Wu"
    assert after["four_pillars"][1]["branch"]["name"] == "Wei"


def test_day_master(chart):
    dm = chart["day_master_strength"]
    assert chart["day_master"] == "Ji"
    assert (dm["element"], dm["yin_yang"]) == ("Earth", "Yin")
    assert dm["seasonal_state"] == "prospers"   # Ji Earth in the Earth month Wei


def test_ten_gods_of_the_visible_stems(chart):
    got = {k: v["stem"]["name"] for k, v in chart["ten_gods"].items()}
    assert got == {
        "year": "Zheng Guan",    # Jia yang Wood controls Ji yin Earth, opposite polarity
        "month": "Shi Shen",     # Ji generates Xin Metal, both yin
        "day": "Day Master",
        "hour": "Zheng Yin",     # Bing yang Fire generates Ji yin Earth, opposite polarity
    }


def test_relations(chart):
    rel = chart["relations"]
    assert {tuple(r["branches"]) for r in rel["branch_harms"]} == {("Zi", "Wei")}
    assert {tuple(sorted(r["stems"])) for r in rel["stem_combinations"]} == {
        ("Ji", "Jia"), ("Bing", "Xin")}
    assert rel["branch_clashes"] == []


# --- the reason hour_pillar_time_basis is configurable ---------------------

def test_hour_pillar_splits_civil_from_solar(chart):
    """Belgrade 1984-07-24 was on CEST, so 05:10 local is 03:10 UTC.

    Longitude 20.465 puts local mean solar time at about 04:32, which is
    before 05:00 and therefore in Yin rather than Mao. The civil clock alone
    says Mao. That is a methodology split, not a rounding difference, and it
    is reported rather than resolved silently.
    """
    alts = chart["hour_pillar_sensitivity"]["by_time_basis"]
    assert alts["civil_clock"]["branch"] == "Mao"
    assert alts["local_mean_solar_time"]["branch"] == "Yin"
    assert alts["true_solar_time"]["branch"] == "Yin"
    assert alts["standard_time_no_dst"]["branch"] == "Yin"
    assert chart["hour_pillar_sensitivity"]["school_dependent"] is True


def test_default_basis_is_solar_and_drives_the_hour_pillar(chart):
    assert chart["methodology"]["hour_pillar_time_basis"] == "local_mean_solar_time"
    assert chart["four_pillars"][3]["branch"]["name"] == "Yin"

    civil = compute_bazi(**REFERENCE, config=BaziConfig(hour_pillar_time_basis="civil_clock"))
    assert civil["four_pillars"][3]["combined"]["name"] == "Ding Mao"


def test_dst_is_applied(chart):
    audit = chart["time_resolution"]
    assert audit["dst_active"] is True
    assert audit["utc"] == "1984-07-24T03:10:00Z"
    assert audit["longitude_correction_minutes"] == pytest.approx(81.86, abs=0.05)


def test_hour_branch_rolls_over_at_23_not_midnight():
    late = compute_bazi("1984-07-24", "23:30:00", "Europe/Belgrade", 20.46513,
                        BaziConfig(hour_pillar_time_basis="civil_clock"))
    assert late["four_pillars"][3]["branch"]["name"] == "Zi"


def test_late_zi_day_rollover_is_configurable():
    kept = compute_bazi("1984-07-24", "23:30:00", "Europe/Belgrade", 20.46513,
                        BaziConfig(hour_pillar_time_basis="civil_clock",
                                   late_zi_advances_day=False))
    advanced = compute_bazi("1984-07-24", "23:30:00", "Europe/Belgrade", 20.46513,
                            BaziConfig(hour_pillar_time_basis="civil_clock",
                                       late_zi_advances_day=True))
    a = STEMS.index(kept["four_pillars"][2]["stem"]["name"])
    b = STEMS.index(advanced["four_pillars"][2]["stem"]["name"])
    assert (b - a) % 10 == 1


# --- luck pillars ----------------------------------------------------------

def test_luck_pillars_need_a_gender():
    anon = compute_bazi(**REFERENCE)
    assert anon["luck_pillars"]["available"] is False


def test_luck_pillar_direction_and_start(chart):
    lp = chart["luck_pillars"]
    assert lp["available"] is True
    assert lp["direction"] == "forward"        # yang year stem Jia with male
    assert lp["start_age"] == pytest.approx(4.74, abs=0.05)
    assert lp["pillars"][0]["stem"] == "Ren" and lp["pillars"][0]["branch"] == "Shen"


def test_female_reverses_direction():
    female = compute_bazi(**REFERENCE, config=BaziConfig(gender="female"))
    assert female["luck_pillars"]["direction"] == "backward"
    first = female["luck_pillars"]["pillars"][0]
    assert (first["stem"], first["branch"]) == ("Geng", "Wu")


def test_luck_pillars_step_one_sexagenary_position_at_a_time(chart):
    pillars = chart["luck_pillars"]["pillars"]
    for a, b in zip(pillars, pillars[1:]):
        i = _cycle_index(STEMS.index(a["stem"]), BRANCHES.index(a["branch"]))
        j = _cycle_index(STEMS.index(b["stem"]), BRANCHES.index(b["branch"]))
        assert (j - i) % 60 == 1
        assert b["start_age"] == pytest.approx(a["start_age"] + 10, abs=1e-6)


# --- honesty about scope ---------------------------------------------------

def test_methodology_is_reported(chart):
    m = chart["methodology"]
    assert m["year_boundary"] == "li_chun"
    assert m["month_boundary"] == "jie_solar_terms"
    assert "na_yin" in m["not_implemented"]
    assert "zi_wei_dou_shu" in m["not_implemented"]


def test_strength_issues_no_verdict(chart):
    """Strong/weak is where schools diverge most and where the label would
    carry most of the downstream interpretation, so no label is emitted."""
    dm = chart["day_master_strength"]
    assert "composite_score" in dm and "scale_note" in dm
    assert not any(k in dm for k in ("verdict", "strong", "is_strong", "label"))
