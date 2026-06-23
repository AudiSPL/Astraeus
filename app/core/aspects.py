"""Natal aspect detection. Angles (ASC/MC) are included as targets; their
applying/separating is left null because an angle's longitude rate isn't a
simple body speed.
"""
from .settings import ASPECTS, MINOR_ASPECTS, ORB_BY_BODY, ASPECT_FACTOR


def separation(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


def _orb(name_a: str, name_b: str, aspect: str) -> float:
    base = max(ORB_BY_BODY.get(name_a, 3), ORB_BY_BODY.get(name_b, 3))
    return base * ASPECT_FACTOR[aspect]


def _applying(a, sa, b, sb, angle, dt=0.02):
    if sa is None or sb is None:
        return None
    now = abs(separation(a, b) - angle)
    nxt = abs(separation(a + sa * dt, b + sb * dt) - angle)
    return nxt < now


_ASPECT_WEIGHT = {
    "conjunction": 1.0, "opposition": 1.0, "square": 0.9, "trine": 0.85, "sextile": 0.7,
    "quincunx": 0.5, "semisextile": 0.3, "semisquare": 0.3, "sesquiquadrate": 0.3,
}
_BODY_WEIGHT = {
    "Sun": 1.0, "Moon": 1.0, "ASC": 0.95, "MC": 0.9,
    "Mercury": 0.8, "Venus": 0.8, "Mars": 0.8,
    "Jupiter": 0.7, "Saturn": 0.7,
    "Uranus": 0.6, "Neptune": 0.6, "Pluto": 0.6,
    "Node": 0.5, "Chiron": 0.45, "Lilith": 0.4,
}


def _strength(orb: float, max_orb: float) -> str:
    r = orb / max_orb
    return "tight" if r <= 0.25 else ("moderate" if r <= 0.6 else "wide")


def _score(na: str, nb: str, aspect: str, orb: float, max_orb: float) -> float:
    tightness = max(0.0, 1.0 - orb / max_orb)
    bw = max(_BODY_WEIGHT.get(na, 0.4), _BODY_WEIGHT.get(nb, 0.4))
    aw = _ASPECT_WEIGHT.get(aspect, 0.4)
    return round(tightness * bw * aw, 3)


def detect(points: dict, include_minors: bool = False) -> list[dict]:
    """points: name -> {lon, speed (or None for angles), name}."""
    table = dict(ASPECTS)
    if include_minors:
        table.update(MINOR_ASPECTS)

    names = list(points)
    out = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            A, B = points[names[i]], points[names[j]]
            s = separation(A["lon"], B["lon"])
            for aspect, angle in table.items():
                max_orb = _orb(A["name"], B["name"], aspect)
                d = abs(s - angle)
                if d <= max_orb:
                    out.append({
                        "a": A["name"], "b": B["name"], "type": aspect,
                        "exact_deg": angle, "orb": round(d, 3),
                        "strength": _strength(d, max_orb),
                        "score": _score(A["name"], B["name"], aspect, d, max_orb),
                        "applying": _applying(A["lon"], A.get("speed"),
                                              B["lon"], B.get("speed"), angle),
                    })
    out.sort(key=lambda x: -x["score"])
    return out
