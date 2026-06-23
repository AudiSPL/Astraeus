"""Download the Swiss Ephemeris data files needed for accurate, Chiron-capable
charts (births ~1800-2399). Run once: python scripts/fetch_ephe.py
"""
import os, urllib.request

BASE = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"
FILES = ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]  # planets, moon, asteroids(Chiron)
DEST = os.path.join(os.path.dirname(__file__), "..", "ephe")
os.makedirs(DEST, exist_ok=True)
for f in FILES:
    out = os.path.join(DEST, f)
    if os.path.exists(out):
        print("exists", f); continue
    print("downloading", f); urllib.request.urlretrieve(BASE + f, out)
print("done ->", os.path.abspath(DEST))
