"""Runtime config. Auto-detects whether real Swiss Ephemeris data files are
present; falls back to the Moshier model (no files) so the service still runs.

Moshier mode: reduced precision and NO Chiron. Run scripts/fetch_ephe.py to get
the .se1 files and unlock full accuracy.
"""
import os

# Repo-root/ephe by default. Override with EPHE_PATH.
_HERE = os.path.dirname(os.path.abspath(__file__))
EPHE_PATH = os.environ.get("EPHE_PATH", os.path.join(_HERE, "..", "..", "ephe"))

# Files that signal full Swiss-Ephemeris availability.
_REQUIRED = ["sepl_18.se1", "semo_18.se1"]
HAS_SWISS_FILES = all(os.path.exists(os.path.join(EPHE_PATH, f)) for f in _REQUIRED)
EPHE_MODE = "swiss_ephemeris" if HAS_SWISS_FILES else "moshier"

# Simple bearer auth for the single agent consumer. Set a real value in prod.
API_KEY = os.environ.get("ASTRAEUS_API_KEY", "dev-key")
REQUIRE_AUTH = os.environ.get("ASTRAEUS_REQUIRE_AUTH", "false").lower() == "true"
