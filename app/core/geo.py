"""Minimal geocoding by static lookup. 95% of charts are Belgrade, so no live
geocoder is used (keeps the calc deterministic and dependency-free).

To add a city: append (lat, lon, IANA_timezone). Or pass explicit
latitude/longitude/timezone in the request to bypass the table entirely.
"""

DEFAULT_CITY = "belgrade"

CITIES = {
    # Serbia / region
    "belgrade":   (44.80401, 20.46513, "Europe/Belgrade"),
    "novi sad":   (45.25167, 19.83694, "Europe/Belgrade"),
    "nis":        (43.32472, 21.90333, "Europe/Belgrade"),
    "kragujevac": (44.01667, 20.91667, "Europe/Belgrade"),
    "subotica":   (46.10000, 19.66667, "Europe/Belgrade"),
    "banja luka": (44.77222, 17.19139, "Europe/Sarajevo"),
    "sarajevo":   (43.85000, 18.38333, "Europe/Sarajevo"),
    "podgorica":  (42.44111, 19.26361, "Europe/Podgorica"),
    "zagreb":     (45.81444, 15.97798, "Europe/Zagreb"),
    "skopje":     (41.99646, 21.43141, "Europe/Skopje"),
    # a few internationals for testing
    "london":     (51.50735, -0.12776, "Europe/London"),
    "vienna":     (48.20849, 16.37208, "Europe/Vienna"),
    "berlin":     (52.52000, 13.40500, "Europe/Berlin"),
    "new york":   (40.71278, -74.00597, "America/New_York"),
}


def resolve(name: str | None):
    """Return (lat, lon, tz) for a city name, or None if not in the table.

    Matches case-insensitively on the part before the first comma, so
    'Belgrade, Serbia' resolves to 'belgrade'.
    """
    if not name:
        return None
    key = name.strip().lower().split(",")[0].strip()
    return CITIES.get(key)
