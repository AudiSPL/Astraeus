"""Build the validation block. validated_for_interpretation is the single gate
the agent checks before saying anything.

forecast, solar_return, and synastry are all hard gates, same as transit: if
requested and the computation doesn't complete, validated_for_interpretation
is false.
"""


def build(natal_complete: bool, time_accuracy: str,
          transit_requested: bool, transit_complete: bool,
          forecast_requested: bool, forecast_complete: bool = False,
          solar_return_requested: bool = False, solar_return_complete: bool = False,
          synastry_requested: bool = False, synastry_complete: bool = False) -> dict:
    natal_validated = natal_complete and time_accuracy != "unknown"
    transits_validated = transit_requested and transit_complete
    forecast_validated = forecast_requested and forecast_complete
    solar_return_validated = solar_return_requested and solar_return_complete
    synastry_validated = synastry_requested and synastry_complete

    reasons = []
    if not natal_validated:
        if time_accuracy == "unknown":
            reasons.append("birth time unknown: ASC, MC and houses are unreliable")
        else:
            reasons.append("natal computation incomplete")
    if transit_requested and not transits_validated:
        reasons.append("transit data missing")
    if forecast_requested and not forecast_validated:
        reasons.append("forecast data missing")
    if solar_return_requested and not solar_return_validated:
        reasons.append("solar return data missing")
    if synastry_requested and not synastry_validated:
        reasons.append("synastry data missing")

    master = (natal_validated
              and (not transit_requested or transits_validated)
              and (not forecast_requested or forecast_validated)
              and (not solar_return_requested or solar_return_validated)
              and (not synastry_requested or synastry_validated))

    return {
        "validated_for_interpretation": master,
        "natal_validated": natal_validated,
        "transits_validated": transits_validated,
        "forecast_validated": forecast_validated,
        "solar_return_validated": solar_return_validated,
        "synastry_validated": synastry_validated,
        "reasons": reasons,
    }


def check_chinese_astrology(block: dict | None) -> tuple[bool, list[str]]:
    """Light validation for the optional chinese_astrology block.

    Approximation warnings alone do not invalidate the block. Missing structural
    fields or a top-level calculation error do.
    """
    if block is None:
        return False, ["chinese astrology requested but block is missing"]

    reasons: list[str] = []
    if block.get("error"):
        reasons.append(f"chinese astrology calculation error: {block['error']}")

    year_pillar = block.get("year_pillar") or {}
    stem = year_pillar.get("stem")
    branch = year_pillar.get("branch")
    combined = year_pillar.get("combined") or {}

    if not stem:
        reasons.append("chinese astrology missing year_pillar.stem")
    if not branch:
        reasons.append("chinese astrology missing year_pillar.branch")
    if not combined.get("characters"):
        reasons.append("chinese astrology missing year_pillar.combined.characters")

    return len(reasons) == 0, reasons
