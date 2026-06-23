"""Static astrological settings: signs, rulers, orbs, aspects, version stamps.

Change SETTINGS_VERSION whenever any orb/aspect value below changes, so the
packet meta stays an honest record of how a chart was produced.
"""

CALC_VERSION = "1.0.0"
SETTINGS_VERSION = "orbs-2026-01"

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

SIGN_ELEMENT = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

SIGN_MODALITY = {
    "Aries": "cardinal", "Cancer": "cardinal", "Libra": "cardinal", "Capricorn": "cardinal",
    "Taurus": "fixed", "Leo": "fixed", "Scorpio": "fixed", "Aquarius": "fixed",
    "Gemini": "mutable", "Virgo": "mutable", "Sagittarius": "mutable", "Pisces": "mutable",
}

MODERN_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Pluto",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune",
}

# Major aspects only by default. Quincunx/minors are opt-in (add noise).
ASPECTS = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
MINOR_ASPECTS = {"quincunx": 150, "semisextile": 30, "semisquare": 45, "sesquiquadrate": 135}

# Per-body base orb (degrees) for major aspects; sextile scaled by ASPECT_FACTOR.
# Pair orb = max(orb_a, orb_b) * factor  -> luminaries govern wider orbs.
ORB_BY_BODY = {
    "Sun": 8, "Moon": 8,
    "Mercury": 7, "Venus": 7, "Mars": 7,
    "Jupiter": 6, "Saturn": 6,
    "Uranus": 5, "Neptune": 5, "Pluto": 5,
    "Node": 3, "Chiron": 3, "Lilith": 3,
    "ASC": 6, "MC": 6,
}
ASPECT_FACTOR = {"conjunction": 1.0, "opposition": 1.0, "square": 1.0,
                 "trine": 1.0, "sextile": 0.7,
                 "quincunx": 0.5, "semisextile": 0.4, "semisquare": 0.4, "sesquiquadrate": 0.4}

# Transit orbs are tight (timing, not theme). Keyed by the moving (transit) body.
TRANSIT_ORB = {
    "Uranus": 1.5, "Neptune": 1.5, "Pluto": 1.5,
    "Jupiter": 1.5, "Saturn": 1.5,
    "Sun": 1.0, "Mercury": 1.0, "Venus": 1.0, "Mars": 1.0,
    "Moon": 1.0,            # snapshot only; excluded from forecast scanning
    "Node": 1.0, "Chiron": 1.0,
}

PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars",
           "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
CORE_FOR_BALANCE = PLANETS  # element/modality counts use the 10 planets only

HOUSE_SYS = {"placidus": b"P", "whole_sign": b"W", "koch": b"K", "equal": b"E"}
