"""The `calculation` metadata block.

Everything needed to reproduce a packet, in one place. Today the same
information is scattered: ephemeris and versions in `meta`, coordinates and
timezone in `birth`, zodiac and house system in `settings`, orb policy inside
`transits`, and the ayanamsha nowhere at all because it was hardcoded.

Scattered is not the same as missing, but it is not an audit contract either.
A reader should not have to know that `orb_policy` only appears when a
transit was requested.

This block is additive. `meta`, `birth` and `settings` keep their current
shape so the golden files stay clean; the new block sits beside them. Once
consumers have moved over, the duplicated fields can be removed in a commit
that deliberately updates the goldens.
"""

from __future__ import annotations

from . import ayanamsha as ayanamsha_mod


def build_calculation_block(
    *,
    calc_version: str,
    settings_version: str,
    ephemeris_mode: str,
    tzdata_version: str,
    jd_ut: float,
    zodiac: str,
    ayanamsha: str | None,
    house_system: str,
    node_type: str,
    include_points: list[str],
    latitude: float,
    longitude: float,
    timezone: str,
    aspect_orb_policy: dict | None = None,
    transit_orb_policy: dict | None = None,
    extra_epochs: dict[str, float] | None = None,
) -> dict:
    """Assemble the block.

    extra_epochs maps a label to a Julian day, e.g.
    {"transit": 2461272.9, "solar_return": 2461245.77}. Each gets its own
    ayanamsha value, because the ayanamsha drifts roughly 50 arcseconds a
    year and one figure quoted for three different moments is wrong for at
    least two of them.
    """
    block: dict = {
        "version": calc_version,
        "settings_version": settings_version,
        "ephemeris": ephemeris_mode,
        "tzdata_version": tzdata_version,
        "reference_frame": "geocentric",
        "position_type": "apparent",
        "zodiac": zodiac,
        "ayanamsha": ayanamsha_mod.describe(jd_ut, zodiac, ayanamsha),
        "house_system": house_system,
        "node_type": node_type,
        "include_points": list(include_points),
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
        },
        "orb_policy": {
            "natal_and_own_chart_aspects": aspect_orb_policy,
            "transit_to_natal": transit_orb_policy,
        },
    }

    if zodiac == "sidereal" and extra_epochs:
        block["ayanamsha_by_epoch"] = {
            "natal": block["ayanamsha"],
            **{
                label: ayanamsha_mod.describe(jd, zodiac, ayanamsha)
                for label, jd in extra_epochs.items()
            },
        }

    return block
