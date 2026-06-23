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
