"""BaZi / Four Pillars engine.

Standalone: depends only on pyswisseph and the standard library. It does not
import anything from app.core, so it can be dropped in and tested before the
compute_chart(config) refactor lands.

Methodology is explicit, configurable, and reported in the output. The point
is that a reader can tell which convention produced a pillar, because the
schools genuinely disagree and a silent choice is the same class of error as
sidereal planets with tropical cusps.

Locked conventions:

* Year boundary is Li Chun (sun at 315 deg), NOT Gregorian 1 January and NOT
  Lunar New Year. This is the classical BaZi convention.
* Month boundaries are the twelve jie (節) solar terms at 30-degree intervals
  from 315 deg, NOT Gregorian months.
* Day pillar is the continuous sexagenary count, index = (JDN + 49) % 60 with
  0 = Jia Zi. Verified against 1949-10-01 = Jia Zi, 1900-01-01 = Jia Xu and
  2000-01-01 = Wu Wu.
* Hour pillar time basis is configurable and defaults to local mean solar
  time. See TimeBasis.

Not implemented, deliberately: Na Yin, Zi Wei Dou Shu, and any single verdict
on Day Master strength. The strength block reports its components and the
weights that produced the number rather than a bare label.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import swisseph as swe

# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

STEMS = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]
STEM_CHARS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
STEM_ELEMENT = ["Wood", "Wood", "Fire", "Fire", "Earth", "Earth", "Metal", "Metal", "Water", "Water"]

BRANCHES = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]
BRANCH_CHARS = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
BRANCH_ANIMAL = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
                 "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
BRANCH_ELEMENT = ["Water", "Earth", "Wood", "Wood", "Earth", "Fire",
                  "Fire", "Earth", "Metal", "Metal", "Earth", "Water"]

# Hidden stems (藏干): principal first, then middle, then residual.
HIDDEN_STEMS = {
    "Zi": ["Gui"],
    "Chou": ["Ji", "Gui", "Xin"],
    "Yin": ["Jia", "Bing", "Wu"],
    "Mao": ["Yi"],
    "Chen": ["Wu", "Yi", "Gui"],
    "Si": ["Bing", "Wu", "Geng"],
    "Wu": ["Ding", "Ji"],
    "Wei": ["Ji", "Ding", "Yi"],
    "Shen": ["Geng", "Ren", "Wu"],
    "You": ["Xin"],
    "Xu": ["Wu", "Xin", "Ding"],
    "Hai": ["Ren", "Jia"],
}
# Conventional weighting of hidden stems within a branch.
HIDDEN_WEIGHTS = [1.0, 0.5, 0.25]

GENERATES = {"Wood": "Fire", "Fire": "Earth", "Earth": "Metal", "Metal": "Water", "Water": "Wood"}
CONTROLS = {"Wood": "Earth", "Earth": "Water", "Water": "Fire", "Fire": "Metal", "Metal": "Wood"}

# Solar terms. The twelve jie mark month boundaries; the twelve zhong are
# midpoints and are reported for context only.
JIE = [
    (315, "Li Chun", "立春", "Yin"), (345, "Jing Zhe", "驚蟄", "Mao"),
    (15, "Qing Ming", "清明", "Chen"), (45, "Li Xia", "立夏", "Si"),
    (75, "Mang Zhong", "芒種", "Wu"), (105, "Xiao Shu", "小暑", "Wei"),
    (135, "Li Qiu", "立秋", "Shen"), (165, "Bai Lu", "白露", "You"),
    (195, "Han Lu", "寒露", "Xu"), (225, "Li Dong", "立冬", "Hai"),
    (255, "Da Xue", "大雪", "Zi"), (285, "Xiao Han", "小寒", "Chou"),
]

# Five-tiger rule: stem of the Yin month, keyed by year stem index.
YIN_MONTH_STEM = [2, 4, 6, 8, 0, 2, 4, 6, 8, 0]
# Five-rat rule: stem of the Zi hour, keyed by day stem index.
ZI_HOUR_STEM = [0, 2, 4, 6, 8, 0, 2, 4, 6, 8]

SIX_COMBINATIONS = [("Zi", "Chou", "Earth"), ("Yin", "Hai", "Wood"), ("Mao", "Xu", "Fire"),
                    ("Chen", "You", "Metal"), ("Si", "Shen", "Water"), ("Wu", "Wei", "Earth")]
SIX_CLASHES = [("Zi", "Wu"), ("Chou", "Wei"), ("Yin", "Shen"),
               ("Mao", "You"), ("Chen", "Xu"), ("Si", "Hai")]
SIX_HARMS = [("Zi", "Wei"), ("Chou", "Wu"), ("Yin", "Si"),
             ("Mao", "Chen"), ("Shen", "Hai"), ("You", "Xu")]
THREE_HARMONIES = [(("Shen", "Zi", "Chen"), "Water"), (("Hai", "Mao", "Wei"), "Wood"),
                   (("Yin", "Wu", "Xu"), "Fire"), (("Si", "You", "Chou"), "Metal")]
DIRECTIONAL = [(("Yin", "Mao", "Chen"), "Wood"), (("Si", "Wu", "Wei"), "Fire"),
               (("Shen", "You", "Xu"), "Metal"), (("Hai", "Zi", "Chou"), "Water")]
PUNISH_TRIPLES = [(("Yin", "Si", "Shen"), "uncivilised"), (("Chou", "Xu", "Wei"), "ungrateful")]
PUNISH_PAIR = ("Zi", "Mao", "rude")
PUNISH_SELF = ["Chen", "Wu", "You", "Hai"]
STEM_COMBINATIONS = [("Jia", "Ji", "Earth"), ("Yi", "Geng", "Metal"), ("Bing", "Xin", "Water"),
                     ("Ding", "Ren", "Wood"), ("Wu", "Gui", "Fire")]
STEM_CLASHES = [("Jia", "Geng"), ("Yi", "Xin"), ("Bing", "Ren"), ("Ding", "Gui")]

TEN_GODS = {
    ("same", True): ("Bi Jian", "比肩", "Friend"),
    ("same", False): ("Jie Cai", "劫財", "Rob Wealth"),
    ("output", True): ("Shi Shen", "食神", "Eating God"),
    ("output", False): ("Shang Guan", "傷官", "Hurting Officer"),
    ("wealth", True): ("Pian Cai", "偏財", "Indirect Wealth"),
    ("wealth", False): ("Zheng Cai", "正財", "Direct Wealth"),
    ("officer", True): ("Qi Sha", "七殺", "Seven Killings"),
    ("officer", False): ("Zheng Guan", "正官", "Direct Officer"),
    ("resource", True): ("Pian Yin", "偏印", "Indirect Resource"),
    ("resource", False): ("Zheng Yin", "正印", "Direct Resource"),
}

TimeBasis = Literal["civil_clock", "standard_time_no_dst", "local_mean_solar_time", "true_solar_time"]

DAY_CYCLE_OFFSET = 49  # (JDN + 49) % 60, 0 = Jia Zi


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

@dataclass
class BaziConfig:
    """Every field here is a place where BaZi schools disagree."""

    hour_pillar_time_basis: TimeBasis = "local_mean_solar_time"
    #: True advances the day pillar for births between 23:00 and midnight
    #: (late Zi hour). Schools split on this; False is the more common default.
    late_zi_advances_day: bool = False
    #: Reported only. Nothing here depends on it except Da Yun direction.
    gender: Literal["male", "female", "unspecified"] = "unspecified"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _stem_yang(index: int) -> bool:
    return index % 2 == 0


def _branch_yang(index: int) -> bool:
    return index % 2 == 0


def _stem_index(name: str) -> int:
    return STEMS.index(name)


def _sun_longitude(jd_ut: float) -> float:
    return swe.calc_ut(jd_ut, swe.SUN, swe.FLG_SWIEPH)[0][0]


def _solar_term_jd(target_deg: float, near_jd: float) -> float:
    """Julian day when the Sun's apparent longitude reaches target_deg.

    Daily scan for the sign change, then bisection. The jump guard rejects the
    360-degree wrap, which would otherwise register as a crossing.
    """
    def diff(jd: float) -> float:
        return (_sun_longitude(jd) - target_deg + 180.0) % 360.0 - 180.0

    lo = near_jd - 200.0
    prev = diff(lo)
    for n in range(1, 401):
        hi = lo + 1.0
        cur = diff(hi)
        if prev < 0 <= cur and abs(cur - prev) < 90:
            a, b = lo, hi
            for _ in range(60):
                mid = (a + b) / 2
                if diff(mid) < 0:
                    a = mid
                else:
                    b = mid
                if b - a < 1e-9:
                    break
            return (a + b) / 2
        lo, prev = hi, cur
    raise ValueError(f"solar term {target_deg} not found near JD {near_jd}")


def _month_branch_for(jd_ut: float) -> tuple[str, dict]:
    """Which jie period contains this instant."""
    lon = _sun_longitude(jd_ut)
    for deg, name, char, branch in JIE:
        end = (deg + 30) % 360
        inside = (deg <= lon < end) if deg < end else (lon >= deg or lon < end)
        if inside:
            start_jd = _solar_term_jd(deg, jd_ut)
            if start_jd > jd_ut:
                start_jd = _solar_term_jd(deg, jd_ut - 365.0)
            return branch, {
                "name": name, "characters": char, "sun_longitude_deg": deg,
                "started_utc": _jd_to_iso(start_jd),
            }
    raise ValueError(f"no jie period for sun longitude {lon}")


def _jd_to_iso(jd: float) -> str:
    y, m, d, h = swe.revjul(jd)
    total = round(h * 3600)
    hh, rem = divmod(total, 3600)
    mm, ss = divmod(rem, 60)
    if hh >= 24:  # guard the rounding rollover
        return (datetime(y, m, d, tzinfo=timezone.utc) + timedelta(days=1)).strftime(
            "%Y-%m-%dT00:00:00Z")
    return f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}:{ss:02d}Z"


def _element_relation(from_el: str, to_el: str) -> str:
    if from_el == to_el:
        return "same"
    if GENERATES[to_el] == from_el:
        return "resource"      # to_el generates the day master
    if GENERATES[from_el] == to_el:
        return "output"        # day master generates to_el
    if CONTROLS[from_el] == to_el:
        return "wealth"        # day master controls to_el
    return "officer"           # to_el controls the day master


def _ten_god(day_master_stem: str, other_stem: str) -> dict:
    dm_i, o_i = _stem_index(day_master_stem), _stem_index(other_stem)
    relation = _element_relation(STEM_ELEMENT[dm_i], STEM_ELEMENT[o_i])
    same_polarity = _stem_yang(dm_i) == _stem_yang(o_i)
    name, char, english = TEN_GODS[(relation, same_polarity)]
    return {"stem": other_stem, "name": name, "characters": char, "english": english,
            "relation": relation, "same_polarity": same_polarity}


# --------------------------------------------------------------------------
# Time basis
# --------------------------------------------------------------------------

def _resolve_hour_time(local: datetime, longitude: float, basis: TimeBasis) -> dict:
    """Return the instant used for the hour branch, plus an audit trail."""
    utc = local.astimezone(timezone.utc)
    dst_offset = local.dst() or timedelta(0)
    standard = local - dst_offset

    lmt_offset = timedelta(hours=longitude / 15.0)
    lmt = utc.replace(tzinfo=None) + lmt_offset

    jd = swe.julday(utc.year, utc.month, utc.day,
                    utc.hour + utc.minute / 60 + utc.second / 3600)
    eot_days = swe.time_equ(jd)  # pyswisseph returns the value directly, in days
    true_solar = lmt + timedelta(days=eot_days)

    chosen = {
        "civil_clock": local.replace(tzinfo=None),
        "standard_time_no_dst": standard.replace(tzinfo=None),
        "local_mean_solar_time": lmt,
        "true_solar_time": true_solar,
    }[basis]

    return {
        "used": chosen,
        "audit": {
            "time_basis": basis,
            "civil_clock": local.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dst_active": dst_offset != timedelta(0),
            "standard_time_no_dst": standard.strftime("%Y-%m-%dT%H:%M:%S"),
            "local_mean_solar_time": lmt.strftime("%Y-%m-%dT%H:%M:%S"),
            "true_solar_time": true_solar.strftime("%Y-%m-%dT%H:%M:%S"),
            "longitude_correction_minutes": round(longitude / 15.0 * 60, 2),
            "equation_of_time_minutes": round(eot_days * 24 * 60, 2),
        },
    }


def _hour_branch_index(moment: datetime) -> int:
    """Zi runs 23:00-01:00, so the hour index rolls over at 23:00."""
    return ((moment.hour + 1) % 24) // 2


# --------------------------------------------------------------------------
# Pillars
# --------------------------------------------------------------------------

def _pillar(stem_i: int, branch_i: int, label: str) -> dict:
    s, b = stem_i % 10, branch_i % 12
    hidden = [_h for _h in HIDDEN_STEMS[BRANCHES[b]]]
    return {
        "pillar": label,
        "stem": {"name": STEMS[s], "characters": STEM_CHARS[s],
                 "element": STEM_ELEMENT[s], "yin_yang": "Yang" if _stem_yang(s) else "Yin"},
        "branch": {"name": BRANCHES[b], "characters": BRANCH_CHARS[b],
                   "animal": BRANCH_ANIMAL[b], "element": BRANCH_ELEMENT[b],
                   "yin_yang": "Yang" if _branch_yang(b) else "Yin",
                   "hidden_stems": [
                       {"stem": h, "characters": STEM_CHARS[_stem_index(h)],
                        "element": STEM_ELEMENT[_stem_index(h)],
                        "role": ["principal", "middle", "residual"][i],
                        "weight": HIDDEN_WEIGHTS[i]}
                       for i, h in enumerate(hidden)]},
        "combined": {"name": f"{STEMS[s]} {BRANCHES[b]}",
                     "characters": f"{STEM_CHARS[s]}{BRANCH_CHARS[b]}",
                     "cycle_index": _cycle_index(s, b)},
    }


def _cycle_index(stem_i: int, branch_i: int) -> int:
    for n in range(60):
        if n % 10 == stem_i and n % 12 == branch_i:
            return n
    raise ValueError("invalid stem/branch pair")


# --------------------------------------------------------------------------
# Relations
# --------------------------------------------------------------------------

def _relations(pillars: list[dict]) -> dict:
    labels = [p["pillar"] for p in pillars]
    branches = [p["branch"]["name"] for p in pillars]
    stems = [p["stem"]["name"] for p in pillars]

    def pairs(seq):
        return [(i, j) for i in range(len(seq)) for j in range(i + 1, len(seq))]

    out: dict[str, list] = {"branch_combinations": [], "branch_clashes": [], "branch_harms": [],
                            "three_harmonies": [], "directional_combinations": [],
                            "punishments": [], "stem_combinations": [], "stem_clashes": []}

    for i, j in pairs(branches):
        a, b = branches[i], branches[j]
        for x, y, el in SIX_COMBINATIONS:
            if {a, b} == {x, y}:
                out["branch_combinations"].append(
                    {"between": [labels[i], labels[j]], "branches": [a, b], "produces": el})
        for x, y in SIX_CLASHES:
            if {a, b} == {x, y}:
                out["branch_clashes"].append({"between": [labels[i], labels[j]], "branches": [a, b]})
        for x, y in SIX_HARMS:
            if {a, b} == {x, y}:
                out["branch_harms"].append({"between": [labels[i], labels[j]], "branches": [a, b]})
        if {a, b} == {PUNISH_PAIR[0], PUNISH_PAIR[1]}:
            out["punishments"].append(
                {"type": PUNISH_PAIR[2], "between": [labels[i], labels[j]], "branches": [a, b]})

    for triple, el in THREE_HARMONIES:
        present = [labels[k] for k, b in enumerate(branches) if b in triple]
        if len({b for b in branches if b in triple}) == 3:
            out["three_harmonies"].append({"branches": list(triple), "produces": el,
                                           "complete": True, "pillars": present})
        elif len({b for b in branches if b in triple}) == 2:
            out["three_harmonies"].append({"branches": sorted({b for b in branches if b in triple}),
                                           "produces": el, "complete": False, "pillars": present})

    for triple, el in DIRECTIONAL:
        if len({b for b in branches if b in triple}) == 3:
            out["directional_combinations"].append({"branches": list(triple), "produces": el,
                                                    "complete": True})

    for triple, kind in PUNISH_TRIPLES:
        found = {b for b in branches if b in triple}
        if len(found) >= 2:
            out["punishments"].append({"type": kind, "branches": sorted(found),
                                       "complete": len(found) == 3})
    for b in PUNISH_SELF:
        if branches.count(b) >= 2:
            out["punishments"].append({"type": "self", "branches": [b, b],
                                       "pillars": [labels[k] for k, x in enumerate(branches) if x == b]})

    for i, j in pairs(stems):
        a, b = stems[i], stems[j]
        for x, y, el in STEM_COMBINATIONS:
            if {a, b} == {x, y}:
                out["stem_combinations"].append(
                    {"between": [labels[i], labels[j]], "stems": [a, b], "produces": el})
        for x, y in STEM_CLASHES:
            if {a, b} == {x, y}:
                out["stem_clashes"].append({"between": [labels[i], labels[j]], "stems": [a, b]})

    return out


# --------------------------------------------------------------------------
# Five elements and Day Master strength
# --------------------------------------------------------------------------

def _five_elements(pillars: list[dict]) -> dict:
    visible = {e: 0.0 for e in ("Wood", "Fire", "Earth", "Metal", "Water")}
    weighted = dict(visible)
    for p in pillars:
        visible[p["stem"]["element"]] += 1
        weighted[p["stem"]["element"]] += 1.0
        visible[p["branch"]["element"]] += 1
        for h in p["branch"]["hidden_stems"]:
            weighted[h["element"]] += h["weight"]
    return {
        "visible_counts": {k: int(v) for k, v in visible.items()},
        "weighted_with_hidden_stems": {k: round(v, 3) for k, v in weighted.items()},
        "weighting_note": "stems 1.0; hidden stems 1.0/0.5/0.25 by principal/middle/residual. "
                          "Branch surface elements are counted in visible_counts only, to avoid "
                          "double-counting them against their own hidden stems.",
    }


SEASON_SUPPORT = {  # month branch element -> how it treats each day-master element
    "prospers": 1.0, "supported": 0.6, "neutral": 0.3, "weakened": 0.1, "exhausted": 0.0,
}


def _day_master_strength(pillars: list[dict], day_master: str) -> dict:
    dm_i = _stem_index(day_master)
    dm_el = STEM_ELEMENT[dm_i]
    month_el = pillars[1]["branch"]["element"]

    if month_el == dm_el:
        season, score = "prospers", 1.0
    elif GENERATES[month_el] == dm_el:
        season, score = "supported", 0.6
    elif GENERATES[dm_el] == month_el:
        season, score = "exhausted", 0.1
    elif CONTROLS[month_el] == dm_el:
        season, score = "weakened", 0.0
    else:
        season, score = "neutral", 0.3

    roots = []
    for p in pillars:
        for h in p["branch"]["hidden_stems"]:
            if h["element"] == dm_el:
                roots.append({"pillar": p["pillar"], "branch": p["branch"]["name"],
                              "stem": h["stem"], "role": h["role"], "weight": h["weight"]})
    root_score = sum(r["weight"] for r in roots)

    allies = sum(1 for i, p in enumerate(pillars) if i != 2
                 and p["stem"]["element"] in (dm_el, {v: k for k, v in GENERATES.items()}[dm_el]))

    total = round(score * 2 + root_score + allies * 0.5, 3)
    return {
        "day_master": day_master,
        "element": dm_el,
        "yin_yang": "Yang" if _stem_yang(dm_i) else "Yin",
        "seasonal_state": season,
        "seasonal_score": score,
        "roots_in_branches": roots,
        "root_score": round(root_score, 3),
        "supporting_stems": allies,
        "composite_score": total,
        "scale_note": "One convention among several, shown with its components so the number "
                      "can be recomputed or disagreed with. No strong/weak verdict is issued: "
                      "schools set that threshold differently and the label carries most of the "
                      "downstream interpretation.",
    }


# --------------------------------------------------------------------------
# Da Yun
# --------------------------------------------------------------------------

def _luck_pillars(local: datetime, year_stem_i: int, month_stem_i: int, month_branch_i: int,
                  gender: str, count: int = 10) -> dict:
    if gender not in ("male", "female"):
        return {"available": False,
                "reason": "gender is required to determine luck-pillar direction",
                "pillars": []}

    year_is_yang = _stem_yang(year_stem_i)
    forward = (year_is_yang and gender == "male") or (not year_is_yang and gender == "female")

    utc = local.astimezone(timezone.utc)
    jd = swe.julday(utc.year, utc.month, utc.day,
                    utc.hour + utc.minute / 60 + utc.second / 3600)
    lon = _sun_longitude(jd)

    boundary = next(d for d, *_ in JIE
                    if ((d <= lon < (d + 30) % 360) if d < (d + 30) % 360
                        else (lon >= d or lon < (d + 30) % 360)))
    if forward:
        target = (boundary + 30) % 360
        term_jd = _solar_term_jd(target, jd + 15)
        days = term_jd - jd
    else:
        term_jd = _solar_term_jd(boundary, jd - 15)
        if term_jd > jd:
            term_jd = _solar_term_jd(boundary, jd - 365)
        days = jd - term_jd

    start_years = days / 3.0
    step = 1 if forward else -1

    pillars = []
    for n in range(1, count + 1):
        s = (month_stem_i + step * n) % 10
        b = (month_branch_i + step * n) % 12
        age = start_years + (n - 1) * 10
        pillars.append({
            "index": n,
            "start_age": round(age, 2),
            "end_age": round(age + 10, 2),
            "start_year": local.year + int(age),
            "stem": STEMS[s], "branch": BRANCHES[b],
            "characters": f"{STEM_CHARS[s]}{BRANCH_CHARS[b]}",
            "stem_element": STEM_ELEMENT[s], "branch_element": BRANCH_ELEMENT[b],
        })

    return {
        "available": True,
        "direction": "forward" if forward else "backward",
        "direction_rule": "yang year stem with male, or yin year stem with female, counts forward",
        "days_to_boundary_term": round(days, 4),
        "start_age": round(start_years, 2),
        "conversion": "three days equal one year",
        "pillars": pillars,
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def compute_bazi(date: str, time: str, timezone_name: str, longitude: float,
                 config: BaziConfig | None = None) -> dict:
    """Full Four Pillars chart.

    date/time are local civil values, e.g. "1984-07-24" and "05:10:00".
    """
    cfg = config or BaziConfig()
    tz = ZoneInfo(timezone_name)
    naive = datetime.fromisoformat(f"{date}T{time}")
    local = naive.replace(tzinfo=tz)

    resolved = _resolve_hour_time(local, longitude, cfg.hour_pillar_time_basis)
    moment = resolved["used"]

    utc = local.astimezone(timezone.utc)
    jd_ut = swe.julday(utc.year, utc.month, utc.day,
                       utc.hour + utc.minute / 60 + utc.second / 3600)

    # Year: Li Chun boundary.
    li_chun_this = _solar_term_jd(315, swe.julday(local.year, 2, 4, 12.0))
    bazi_year = local.year if jd_ut >= li_chun_this else local.year - 1
    year_stem_i = (bazi_year - 4) % 10
    year_branch_i = (bazi_year - 4) % 12

    # Month: jie boundary + five-tiger rule.
    month_branch_name, term = _month_branch_for(jd_ut)
    month_branch_i = BRANCHES.index(month_branch_name)
    months_from_yin = (month_branch_i - 2) % 12
    month_stem_i = (YIN_MONTH_STEM[year_stem_i] + months_from_yin) % 10

    # Day: continuous sexagenary count on the civil date.
    day_jdn = int(swe.julday(local.year, local.month, local.day, 12.0))
    if cfg.late_zi_advances_day and moment.hour == 23:
        day_jdn += 1
    day_cycle = (day_jdn + DAY_CYCLE_OFFSET) % 60
    day_stem_i, day_branch_i = day_cycle % 10, day_cycle % 12

    # Hour: five-rat rule on the chosen time basis.
    hour_branch_i = _hour_branch_index(moment)
    hour_stem_i = (ZI_HOUR_STEM[day_stem_i] + hour_branch_i) % 10

    pillars = [
        _pillar(year_stem_i, year_branch_i, "year"),
        _pillar(month_stem_i, month_branch_i, "month"),
        _pillar(day_stem_i, day_branch_i, "day"),
        _pillar(hour_stem_i, hour_branch_i, "hour"),
    ]
    day_master = STEMS[day_stem_i]

    ten_gods = {
        p["pillar"]: {
            "stem": _ten_god(day_master, p["stem"]["name"]),
            "hidden": [_ten_god(day_master, h["stem"]) for h in p["branch"]["hidden_stems"]],
        } for p in pillars
    }
    ten_gods["day"]["stem"] = {"stem": day_master, "name": "Day Master", "characters": "日主",
                               "english": "Day Master", "relation": "self", "same_polarity": True}

    # Alternative hour pillars, so a methodology disagreement is visible
    # rather than silently resolved.
    alternatives = {}
    for basis in ("civil_clock", "standard_time_no_dst", "local_mean_solar_time", "true_solar_time"):
        alt_moment = _resolve_hour_time(local, longitude, basis)["used"]
        alt_b = _hour_branch_index(alt_moment)
        alt_s = (ZI_HOUR_STEM[day_stem_i] + alt_b) % 10
        alternatives[basis] = {
            "clock": alt_moment.strftime("%H:%M:%S"),
            "pillar": f"{STEMS[alt_s]} {BRANCHES[alt_b]}",
            "characters": f"{STEM_CHARS[alt_s]}{BRANCH_CHARS[alt_b]}",
            "branch": BRANCHES[alt_b],
        }
    schools_disagree = len({v["branch"] for v in alternatives.values()}) > 1

    return {
        "system": "bazi_four_pillars",
        "methodology": {
            "version": "1.0.0",
            "year_boundary": "li_chun",
            "month_boundary": "jie_solar_terms",
            "day_cycle": f"continuous sexagenary, (JDN + {DAY_CYCLE_OFFSET}) % 60, 0 = Jia Zi",
            "hour_pillar_time_basis": cfg.hour_pillar_time_basis,
            "late_zi_advances_day": cfg.late_zi_advances_day,
            "ephemeris": "swiss_ephemeris",
            "not_implemented": ["na_yin", "zi_wei_dou_shu", "annual_and_monthly_pillar_timing"],
        },
        "input": {
            "local": local.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "longitude": longitude,
            "timezone": timezone_name,
        },
        "time_resolution": resolved["audit"],
        "bazi_year": bazi_year,
        "li_chun_utc": _jd_to_iso(li_chun_this),
        "month_solar_term": term,
        "four_pillars": pillars,
        "day_master": day_master,
        "ten_gods": ten_gods,
        "five_elements": _five_elements(pillars),
        "day_master_strength": _day_master_strength(pillars, day_master),
        "relations": _relations(pillars),
        "luck_pillars": _luck_pillars(local, year_stem_i, month_stem_i, month_branch_i, cfg.gender),
        "hour_pillar_sensitivity": {
            "by_time_basis": alternatives,
            "school_dependent": schools_disagree,
            "note": "Different time bases give different hour branches for this birth. "
                    "The chosen basis is in methodology.hour_pillar_time_basis; the others "
                    "are shown rather than hidden." if schools_disagree
                    else "All four time bases agree on the hour branch for this birth.",
        },
        "warnings": [],
    }


if __name__ == "__main__":
    print(json.dumps(compute_bazi("1984-07-24", "05:10:00", "Europe/Belgrade", 20.46513,
                                  BaziConfig(gender="male")), indent=2, ensure_ascii=False))
