"""Phase 3: forward-looking forecast scanner.

Finds exact transit-to-natal aspect dates and retrograde/direct stations for
the outer-planet movers (transits.FORECAST_MOVERS — Jupiter through Pluto, no
Moon/Mars, see transits.py for why) across an arbitrary date range, plus solar
and lunar eclipses in the same window with their aspects to the natal chart.

This is glue + eclipse search, not new numerics: the date-finding itself reuses
transits.exact_hits / transits.stations, both already tested.
"""
import swisseph as swe

from .ephemeris import IPL, base_flag, init, _LOCK, position
from .settings import ASPECTS
from .aspects import separation
from .transits import exact_hits, stations, FORECAST_MOVERS
from .timeutil import jd_to_utc_iso as _jd_to_iso

# Eclipses get one flat orb, not the body-scaled transit table: the eclipse
# point itself isn't a moving planet you can catch "applying", and astrological
# convention treats the degree as active within several degrees, not ~1°.
ECLIPSE_ORB = 5.0
ECLIPSE_ASPECTS = {"conjunction": 0, "opposition": 180, "square": 90}

_SOLAR_KIND = [(swe.ECL_TOTAL, "total"), (swe.ECL_ANNULAR_TOTAL, "hybrid"),
              (swe.ECL_ANNULAR, "annular"), (swe.ECL_PARTIAL, "partial")]
_LUNAR_KIND = [(swe.ECL_TOTAL, "total"), (swe.ECL_PARTIAL, "partial"),
              (swe.ECL_PENUMBRAL, "penumbral")]


def mover_hits(natal_points: dict, jd0: float, jd1: float, zodiac: str,
              movers: list | None = None, step: float = 1.0) -> list[dict]:
    """Exact transit-to-natal aspect dates for every (mover, natal point,
    aspect) combination in [jd0, jd1]."""
    with _LOCK:
        init()
        if zodiac == "sidereal":
            swe.set_sid_mode(swe.SIDM_LAHIRI)
        flag = base_flag(zodiac)
        movers = movers or FORECAST_MOVERS
        out = []
        for mv in movers:
            ipl = IPL[mv]
            for nn, N in natal_points.items():
                for aspect, angle in ASPECTS.items():
                    for jd in exact_hits(ipl, N["lon"], angle, flag, jd0, jd1, step):
                        out.append({
                            "date": _jd_to_iso(jd),
                            "julian_day_ut": round(jd, 6),
                            "transit": mv, "natal": nn, "type": aspect,
                        })
        out.sort(key=lambda x: x["julian_day_ut"])
        return out


def station_events(jd0: float, jd1: float, zodiac: str,
                   movers: list | None = None, step: float = 1.0) -> list[dict]:
    with _LOCK:
        init()
        if zodiac == "sidereal":
            swe.set_sid_mode(swe.SIDM_LAHIRI)
        flag = base_flag(zodiac)
        movers = movers or FORECAST_MOVERS
        out = []
        for mv in movers:
            for ev in stations(IPL[mv], flag, jd0, jd1, step):
                out.append({
                    "date": _jd_to_iso(ev["jd"]),
                    "julian_day_ut": round(ev["jd"], 6),
                    "planet": mv, "direction": ev["direction"],
                })
        out.sort(key=lambda x: x["julian_day_ut"])
        return out


def _eclipse_kind(eclipse_type: str, retflag: int) -> str:
    table = _SOLAR_KIND if eclipse_type == "solar" else _LUNAR_KIND
    for bit, name in table:
        if retflag & bit:
            return name
    return "unknown"


def _eclipse_record(eclipse_type: str, retflag: int, jd: float, lon: float,
                    natal_points: dict) -> dict:
    hits = []
    for nn, N in natal_points.items():
        s = separation(lon, N["lon"])
        for aspect, angle in ECLIPSE_ASPECTS.items():
            d = abs(s - angle)
            if d <= ECLIPSE_ORB:
                hits.append({"natal": nn, "type": aspect, "orb": round(d, 3)})
    hits.sort(key=lambda x: x["orb"])
    return {
        "date": _jd_to_iso(jd),
        "julian_day_ut": round(jd, 6),
        "eclipse_type": eclipse_type,
        "kind": _eclipse_kind(eclipse_type, retflag),
        "ecliptic_lon": round(lon % 360, 4),
        "orb_used": ECLIPSE_ORB,
        "natal_hits": hits,
    }


def eclipses(natal_points: dict, jd0: float, jd1: float) -> list[dict]:
    """Solar (sol_eclipse_when_glob — global, since the degree matters
    astrologically regardless of where on Earth it's visible) and lunar
    (lun_eclipse_when — lunar eclipses are inherently global) eclipses in
    [jd0, jd1]. Eclipse degree = Sun's longitude at solar max (New Moon,
    Sun==Moon), Moon's longitude at lunar max (Full Moon)."""
    with _LOCK:
        init()
        flag = base_flag("tropical")  # eclipse degree is always ecliptic/tropical
        out = []

        t = jd0
        while True:
            retflag, tret = swe.sol_eclipse_when_glob(t, swe.FLG_SWIEPH, 0, False)
            jd_max = tret[0]
            if jd_max == 0 or jd_max > jd1:
                break
            lon, _ = position(jd_max, IPL["Sun"], flag)
            out.append(_eclipse_record("solar", retflag, jd_max, lon, natal_points))
            t = jd_max + 1

        t = jd0
        while True:
            retflag, tret = swe.lun_eclipse_when(t, swe.FLG_SWIEPH, 0, False)
            jd_max = tret[0]
            if jd_max == 0 or jd_max > jd1:
                break
            lon, _ = position(jd_max, IPL["Moon"], flag)
            out.append(_eclipse_record("lunar", retflag, jd_max, lon, natal_points))
            t = jd_max + 1

        out.sort(key=lambda x: x["julian_day_ut"])
        return out


def scan(natal_points: dict, jd0: float, jd1: float, zodiac: str,
        movers: list | None = None, step: float = 1.0) -> dict:
    return {
        "period": {"start": _jd_to_iso(jd0), "end": _jd_to_iso(jd1)},
        "eclipse_orb": ECLIPSE_ORB,
        "movers_used": movers or FORECAST_MOVERS,
        "transits": mover_hits(natal_points, jd0, jd1, zodiac, movers, step),
        "stations": station_events(jd0, jd1, zodiac, movers, step),
        "eclipses": eclipses(natal_points, jd0, jd1),
    }
