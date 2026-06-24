"""Thin Swiss Ephemeris wrapper. Computes planet/point longitudes (with speed,
hence retrograde) and house cusps. No interpretation here.

NOTE on house cusps: this pyswisseph build returns a 12-length, 0-indexed tuple
(cusps[0] == House 1 == ASC). Older bindings returned 13 with a dummy [0]. The
indexing below is correct for the modern build and guarded by the golden test.
"""
import threading

import swisseph as swe

from . import config
from .settings import SIGNS, HOUSE_SYS

# pyswisseph is NOT thread-safe and its ephemeris path is process-global C state.
# FastAPI runs sync endpoints in a threadpool, so we (a) re-assert the path on
# every entry and (b) serialise all swe access with a reentrant lock.
_LOCK = threading.RLock()

# name -> Swiss Ephemeris body id
IPL = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
    "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
    "Chiron": swe.CHIRON,
}
_PLANET_NAMES = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                 "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]


def init():
    """Assert the ephemeris path. Cheap and idempotent — must run on every
    request thread because swe's path is global C state lost across threads."""
    swe.set_ephe_path(config.EPHE_PATH)


def base_flag(zodiac: str):
    f = swe.FLG_SPEED
    f |= swe.FLG_SWIEPH if config.EPHE_MODE == "swiss_ephemeris" else swe.FLG_MOSEPH
    if zodiac == "sidereal":
        f |= swe.FLG_SIDEREAL
    return f


def sign_of(lon: float) -> str:
    return SIGNS[int((lon % 360) // 30)]


def _mk(name: str, lon: float, speed: float) -> dict:
    lon %= 360
    return {"name": name, "lon": round(lon, 6), "sign": sign_of(lon),
            "deg_in_sign": round(lon % 30, 4), "speed": round(speed, 6),
            "retrograde": speed < 0}


def position(jd: float, ipl: int, flag: int):
    xx, _ = swe.calc_ut(jd, ipl, flag)
    return xx[0] % 360, xx[3]


def compute_bodies(jd: float, zodiac: str, node_type: str, include_points: list[str]) -> dict:
    with _LOCK:
        init()
        if zodiac == "sidereal":
            swe.set_sid_mode(swe.SIDM_LAHIRI)
        flag = base_flag(zodiac)
        out = {}
        for n in _PLANET_NAMES:
            lon, sp = position(jd, IPL[n], flag)
            out[n] = _mk(n, lon, sp)

        node_ipl = swe.TRUE_NODE if node_type == "true" else swe.MEAN_NODE
        lon, sp = position(jd, node_ipl, flag)
        out["Node"] = _mk("Node", lon, sp)

        if "chiron" in include_points and config.EPHE_MODE == "swiss_ephemeris":
            try:
                lon, sp = position(jd, swe.CHIRON, flag)
                out["Chiron"] = _mk("Chiron", lon, sp)
            except Exception:
                pass
        if "lilith" in include_points:
            lon, sp = position(jd, swe.MEAN_APOG, flag)
            out["Lilith"] = _mk("Lilith", lon, sp)
        return out


def compute_houses(jd: float, lat: float, lon: float, house_system: str, zodiac: str):
    with _LOCK:
        init()
        hs = HOUSE_SYS[house_system]
        if zodiac == "sidereal":
            cusps, ascmc = swe.houses_ex(jd, lat, lon, hs, swe.FLG_SIDEREAL)
        else:
            cusps, ascmc = swe.houses(jd, lat, lon, hs)
        cusp_lons = [cusps[i] % 360 for i in range(12)]          # H1..H12
        houses = [{"num": i + 1, "cusp_lon": round(cusp_lons[i], 6),
                   "sign": sign_of(cusp_lons[i])} for i in range(12)]
        angles = {
            "asc": {"lon": round(ascmc[0] % 360, 6), "sign": sign_of(ascmc[0]),
                    "deg_in_sign": round(ascmc[0] % 30, 4)},
            "mc": {"lon": round(ascmc[1] % 360, 6), "sign": sign_of(ascmc[1]),
                   "deg_in_sign": round(ascmc[1] % 30, 4)},
        }
        return houses, angles, cusp_lons


def house_of(lon: float, cusp_lons: list[float]) -> int:
    """Which house contains `lon`, given the 12 cusp longitudes (H1..H12)."""
    lon %= 360
    for i in range(12):
        a = cusp_lons[i]
        b = cusp_lons[(i + 1) % 12]
        if a < b:
            if a <= lon < b:
                return i + 1
        else:  # segment wraps past 360
            if lon >= a or lon < b:
                return i + 1
    return 12
