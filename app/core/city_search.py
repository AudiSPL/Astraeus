"""Static city search index for the location-picker autocomplete.

Loads data/cities.json once at import (~2200 cities: Balkan region densely
covered down to ~20k population, the rest of Europe down to ~100k, major
world cities down to ~600k population, plus every national capital
regardless of population). Pure in-memory substring/prefix search, no
network calls, no live geocoding API -- same "deterministic, dependency-free"
philosophy as core.geo, just a much larger table aimed at the UI's
search-as-you-type city picker.

Public API:
    search(query: str, limit: int = 20) -> list[dict]
"""
import json
import re
import unicodedata
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "cities.json"
with open(DATA_PATH, encoding="utf-8") as f:
    _CITIES = json.load(f)


def _normalize(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def search(query: str, limit: int = 20) -> list[dict]:
    """Rank: exact name match, then name-prefix, then alt-name-prefix, then
    name-contains, then alt-name-contains. Within a rank, larger cities first."""
    q = _normalize(query)
    if not q:
        return []
    scored = []
    for c in _CITIES:
        name = c["ascii_name"]
        if name == q:
            rank = 0
        elif name.startswith(q):
            rank = 1
        elif any(a.startswith(q) for a in c["alt_search"]):
            rank = 2
        elif q in name:
            rank = 3
        elif any(q in a for a in c["alt_search"]):
            rank = 4
        else:
            continue
        scored.append((rank, -c["population"], c))
    scored.sort(key=lambda t: (t[0], t[1]))
    out = []
    for _, _, c in scored[:limit]:
        out.append({
            "name": c["name"],
            "country": c["country"],
            "countrycode": c["countrycode"],
            "lat": c["lat"],
            "lon": c["lon"],
            "timezone": c["timezone"],
            "label": f"{c['name']}, {c['country']}",
        })
    return out
