"""Transit positions and transit-to-natal aspects (snapshot), plus the
root-finding utilities the Phase-3 forecast scanner will reuse (exact hit dates,
retrograde stations). These utilities are tested now so the forecast layer
inherits verified math.
"""
import swisseph as swe

from . import config
from .settings import ASPECTS, TRANSIT_ORB, ASPECT_FACTOR
from .ephemeris import position, base_flag, _mk, IPL, init, _LOCK
from .aspects import separation

# Default movers for a transit snapshot (Moon included). Forecast scanning should
# pass movers WITHOUT the Moon (it aspects everything every ~2.4 days = noise).
SNAPSHOT_MOVERS = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                   "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
FORECAST_MOVERS = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]


def transit_bodies(jd: float, zodiac: str, movers=None) -> dict:
    with _LOCK:
        init()
        if zodiac == "sidereal":
            swe.set_sid_mode(swe.SIDM_LAHIRI)
        flag = base_flag(zodiac)
        movers = movers or SNAPSHOT_MOVERS
        out = {}
        for n in movers:
            try:
                lon, sp = position(jd, IPL[n], flag)
                out[n] = _mk(n, lon, sp)
            except Exception:
                pass
        return out


def _transit_orb(mover: str, aspect: str) -> float:
    return TRANSIT_ORB.get(mover, 1.0) * ASPECT_FACTOR[aspect]


_TRANSIT_BODY_WEIGHT = {
    "Pluto": 1.0, "Neptune": 0.95, "Uranus": 0.9, "Saturn": 0.85, "Jupiter": 0.8,
    "Mars": 0.65, "Sun": 0.6, "Venus": 0.55, "Mercury": 0.5, "Moon": 0.4, "Node": 0.5,
}
_TRANSIT_NATAL_WEIGHT = {
    "ASC": 1.0, "MC": 0.95, "Sun": 0.9, "Moon": 0.9,
    "Mercury": 0.75, "Venus": 0.75, "Mars": 0.75,
    "Jupiter": 0.65, "Saturn": 0.65,
    "Node": 0.55, "Chiron": 0.5, "Lilith": 0.4,
    "Uranus": 0.5, "Neptune": 0.5, "Pluto": 0.5,
}
_TRANSIT_ASPECT_WEIGHT = {"conjunction": 1.0, "opposition": 1.0, "square": 0.9,
                           "trine": 0.85, "sextile": 0.7}

ORB_POLICY = {
    "outer_planets_uranus_neptune_pluto": 1.5,
    "jupiter_saturn": 1.5,
    "sun_mercury_venus_mars": 1.0,
    "moon": 1.0,
    "node_chiron": 1.0,
    "aspects": ["conjunction", "opposition", "square", "trine", "sextile"],
}


def transit_to_natal(tbodies: dict, natal_points: dict) -> list[dict]:
    """natal_points: name -> {lon, name} (natal bodies + ASC/MC as fixed targets)."""
    out = []
    for tn, T in tbodies.items():
        for nn, N in natal_points.items():
            s = separation(T["lon"], N["lon"])
            for aspect, angle in ASPECTS.items():
                max_orb = _transit_orb(tn, aspect)
                d = abs(s - angle)
                if d <= max_orb:
                    nxt = abs(separation(T["lon"] + T["speed"] * 0.02, N["lon"]) - angle)
                    tightness = max(0.0, 1.0 - d / max_orb)
                    tw = _TRANSIT_BODY_WEIGHT.get(tn, 0.5)
                    nw = _TRANSIT_NATAL_WEIGHT.get(nn, 0.5)
                    aw = _TRANSIT_ASPECT_WEIGHT.get(aspect, 0.7)
                    applying = nxt < d
                    score = round(tightness * tw * nw * aw * (1.15 if applying else 1.0), 3)
                    out.append({
                        "transit": tn, "natal": nn, "type": aspect,
                        "exact_deg": angle, "orb": round(d, 3),
                        "strength": ("tight" if tightness >= 0.75 else
                                     "moderate" if tightness >= 0.4 else "wide"),
                        "score": score,
                        "applying": applying,
                    })
    out.sort(key=lambda x: -x["score"])
    return out


# --- root-finding utilities (Phase 3 forecast) ---

def _signed(lon_t: float, lon_n: float, angle: float) -> float:
    """Smooth signed distance from the exact aspect, zero at exact.
    Handles the +A / -A mirror (square at 90 and 270, etc.)."""
    d = (lon_t - lon_n) % 360
    target = min({angle, (360 - angle) % 360},
                 key=lambda a: abs(((d - a + 180) % 360) - 180))
    return ((d - target + 180) % 360) - 180


def exact_hits(ipl: int, natal_lon: float, angle: float, flag: int,
               jd0: float, jd1: float, step: float = 1.0) -> list[float]:
    """All exact-aspect Julian Days in [jd0, jd1]. Multiple results = retrograde
    multi-pass. Coarse daily scan detects sign changes; bisection refines."""
    hits = []
    t = jd0
    fp = _signed(position(t, ipl, flag)[0], natal_lon, angle)
    tp = t
    t += step
    while t <= jd1:
        fc = _signed(position(t, ipl, flag)[0], natal_lon, angle)
        # genuine crossing: sign change AND not a wrap discontinuity (~360 jump
        # at the antipode of the aspect). |fc-fp|>90 means the function wrapped,
        # not crossed zero -> skip.
        crossed = (fp == 0 or (fc < 0) != (fp < 0)) and abs(fc - fp) < 90
        if crossed:
            lo, hi, fl = tp, t, fp
            for _ in range(40):
                mid = (lo + hi) / 2
                fm = _signed(position(mid, ipl, flag)[0], natal_lon, angle)
                if (fm < 0) != (fl < 0):
                    hi = mid
                else:
                    lo, fl = mid, fm
            hits.append((lo + hi) / 2)
        fp, tp = fc, t
        t += step
    return hits


def stations(ipl: int, flag: int, jd0: float, jd1: float, step: float = 1.0) -> list[dict]:
    """Retrograde/direct stations (longitude speed crosses zero)."""
    out = []
    t = jd0
    sp = position(t, ipl, flag)[1]
    tp = t
    t += step
    while t <= jd1:
        sc = position(t, ipl, flag)[1]
        if (sc < 0) != (sp < 0):
            lo, hi, sl = tp, t, sp
            for _ in range(40):
                mid = (lo + hi) / 2
                sm = position(mid, ipl, flag)[1]
                if (sm < 0) != (sl < 0):
                    hi = mid
                else:
                    lo, sl = mid, sm
            jd = (lo + hi) / 2
            out.append({"jd": jd, "direction": "retrograde" if sc < 0 else "direct"})
        sp, tp = sc, t
        t += step
    return out
