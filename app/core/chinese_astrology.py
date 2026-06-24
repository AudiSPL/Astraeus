"""Deterministic Chinese zodiac / BaZi year-pillar calculator (basic v1).

Uses Gregorian birth year as a stand-in for the Chinese lunar year boundary.
No interpretive text — structured symbolic data only.
"""
from __future__ import annotations

from datetime import date

REFERENCE_YEAR = 1984  # Jia Zi (甲子) — Wood Rat

YEAR_BOUNDARY_WARNING = (
    "Chinese year boundary is approximated using Gregorian year; "
    "lunar new year / Li Chun boundary not yet implemented."
)

HEAVENLY_STEMS: list[dict[str, str | int]] = [
    {"index": 0, "name": "Jia", "character": "甲", "element": "Wood", "yin_yang": "Yang"},
    {"index": 1, "name": "Yi", "character": "乙", "element": "Wood", "yin_yang": "Yin"},
    {"index": 2, "name": "Bing", "character": "丙", "element": "Fire", "yin_yang": "Yang"},
    {"index": 3, "name": "Ding", "character": "丁", "element": "Fire", "yin_yang": "Yin"},
    {"index": 4, "name": "Wu", "character": "戊", "element": "Earth", "yin_yang": "Yang"},
    {"index": 5, "name": "Ji", "character": "己", "element": "Earth", "yin_yang": "Yin"},
    {"index": 6, "name": "Geng", "character": "庚", "element": "Metal", "yin_yang": "Yang"},
    {"index": 7, "name": "Xin", "character": "辛", "element": "Metal", "yin_yang": "Yin"},
    {"index": 8, "name": "Ren", "character": "壬", "element": "Water", "yin_yang": "Yang"},
    {"index": 9, "name": "Gui", "character": "癸", "element": "Water", "yin_yang": "Yin"},
]

EARTHLY_BRANCHES: list[dict[str, str | int]] = [
    {"index": 0, "name": "Zi", "character": "子", "animal": "Rat", "element": "Water", "yin_yang": "Yang"},
    {"index": 1, "name": "Chou", "character": "丑", "animal": "Ox", "element": "Earth", "yin_yang": "Yin"},
    {"index": 2, "name": "Yin", "character": "寅", "animal": "Tiger", "element": "Wood", "yin_yang": "Yang"},
    {"index": 3, "name": "Mao", "character": "卯", "animal": "Rabbit", "element": "Wood", "yin_yang": "Yin"},
    {"index": 4, "name": "Chen", "character": "辰", "animal": "Dragon", "element": "Earth", "yin_yang": "Yang"},
    {"index": 5, "name": "Si", "character": "巳", "animal": "Snake", "element": "Fire", "yin_yang": "Yin"},
    {"index": 6, "name": "Wu", "character": "午", "animal": "Horse", "element": "Fire", "yin_yang": "Yang"},
    {"index": 7, "name": "Wei", "character": "未", "animal": "Goat", "element": "Earth", "yin_yang": "Yin"},
    {"index": 8, "name": "Shen", "character": "申", "animal": "Monkey", "element": "Metal", "yin_yang": "Yang"},
    {"index": 9, "name": "You", "character": "酉", "animal": "Rooster", "element": "Metal", "yin_yang": "Yin"},
    {"index": 10, "name": "Xu", "character": "戌", "animal": "Dog", "element": "Earth", "yin_yang": "Yang"},
    {"index": 11, "name": "Hai", "character": "亥", "animal": "Pig", "element": "Water", "yin_yang": "Yin"},
]

ELEMENTS = ("Wood", "Fire", "Earth", "Metal", "Water")
YIN_YANG = ("Yin", "Yang")


def _year_from_birth_date(birth_date: str) -> int:
    return date.fromisoformat(birth_date).year


def _element_presence(stem: dict, branch: dict) -> dict[str, int]:
    counts = {el: 0 for el in ELEMENTS}
    for part in (stem, branch):
        counts[str(part["element"])] += 1
    return counts


def _yin_yang_presence(stem: dict, branch: dict) -> dict[str, int]:
    counts = {yy: 0 for yy in YIN_YANG}
    for part in (stem, branch):
        counts[str(part["yin_yang"])] += 1
    return counts


def calculate_chinese_astrology(birth_date: str) -> dict:
    """Return the basic Chinese astrology block for a Gregorian birth date."""
    year = _year_from_birth_date(birth_date)
    stem_index = (year - REFERENCE_YEAR) % 10
    branch_index = (year - REFERENCE_YEAR) % 12

    stem = dict(HEAVENLY_STEMS[stem_index])
    branch = dict(EARTHLY_BRANCHES[branch_index])

    return {
        "system": "chinese_zodiac_basic",
        "calendar_method": "gregorian_year_approximation",
        "year_pillar": {
            "stem": stem,
            "branch": branch,
            "combined": {
                "name": f"{stem['name']} {branch['name']}",
                "characters": f"{stem['character']}{branch['character']}",
            },
        },
        "five_elements_presence": _element_presence(stem, branch),
        "yin_yang_presence": _yin_yang_presence(stem, branch),
        "warnings": [YEAR_BOUNDARY_WARNING],
    }
