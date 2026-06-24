# Astraeus — Calculation API

Deterministic astrology calculation engine. FastAPI + Swiss Ephemeris. The
interpretation layer (a custom GPT, used manually) never calculates — it only
consumes the validated packet this service returns, and must refuse to read a
chart when `validated_for_interpretation` is `false`.

**Status: Phase 1-4 complete.** Natal chart, transit snapshot, secondary
progressions + solar arc, forecast scanner (exact hits + stations + eclipses),
solar return, and synastry + composite are all wired into one endpoint, all
independently hard-gated, all reachable from the local web UI control panel.

## Run it (PowerShell)

### First time only
```powershell
cd C:\Projects\Astraeus
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/fetch_ephe.py        # downloads .se1 data files (usually already bundled)
```

### Every time after
```powershell
cd C:\Projects\Astraeus
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Then open:
- `http://localhost:8000` — the control panel (fill the form, hit Generiši
  paket, copy the JSON straight into the custom GPT).
- `http://localhost:8000/docs` — raw OpenAPI UI, for hitting the endpoint
  directly without the form.

### Tests
```powershell
.venv\Scripts\Activate.ps1
python -m pytest -v
```
All tests expected to pass against the real `.se1` files (not the Moshier
approximation a sandbox without those files would fall back to).

### Env vars (PowerShell syntax, if you ever need them)
```powershell
$env:ASTRAEUS_REQUIRE_AUTH = "true"
$env:ASTRAEUS_API_KEY = "your-key-here"
```
Auth is off by default.

## Accuracy

Full **Swiss Ephemeris** precision when the `.se1` data files are present in
`ephe/`. Without them the service auto-falls back to the **Moshier** model —
reduced precision, no Chiron — and says so in `meta.ephemeris` and
`warnings`.

Birth-time matters: a few minutes of clock error can flip the Ascendant to a
neighboring sign. Set `time_accuracy` honestly on every birth record (`exact`
/ `approx` / `unknown`) — primary and synastry partner alike. `unknown` blocks
interpretation for that chart.

## The web UI

`app/static/ui.html`, served at `GET /`. A single-file, no-build-step control
panel: natal fields always visible, every optional block (transit,
progressions, forecast, solar return, synastry) is a collapsible section with
an enable toggle. Hitting **Generiši paket** POSTs to `/v1/chart-packet` and
renders the response with syntax highlighting, a `validated_for_interpretation`
status lamp, and a one-click copy button — built specifically so the output
can go straight into the custom GPT without manual reformatting.

## Endpoints
GET  /v1/health

GET  /                  control panel UI

POST /v1/chart-packet

### Request

```jsonc
{
  "birth": {
    "date": "1984-07-24", "time": "05:10:00",      // required
    "time_accuracy": "exact",                       // exact | approx | unknown
    "place_label": "Belgrade, Serbia",               // resolved via geo table, OR:
    "latitude": 44.80401, "longitude": 20.46513,     // explicit coords bypass the table
    "timezone": "Europe/Belgrade"                    // IANA id
  },
  "settings": {                                      // all optional, shown with defaults
    "zodiac": "tropical", "house_system": "placidus",
    "node_type": "true", "include_points": ["chiron", "lilith"]
  },

  "transit": {                                        // omit for no transit snapshot
    "date": "2026-06-19", "time": "12:00:00", "timezone": "Europe/London"
  },

  "progressions": { "date": "2026-07-15" },           // secondary + solar arc to this date

  "forecast": {                                        // exact hits + stations + eclipses
    "enabled": true,
    "start_date": "2026-06-20",                        // omit -> defaults to today (UTC)
    "months": 12                                        // OR "end_date": "2027-06-20"
  },

  "solar_return": {                                    // full chart for the year's Sun return
    "year": 2026,
    "city": "New York",                                 // omit -> natal location;
    "latitude": 40.71, "longitude": -74.00,              // or explicit coords, OR neither
    "house_system": "placidus"                           // omit -> same as settings.house_system
  },

  "synastry": {                                          // second chart + comparison
    "enabled": true,
    "partner": {                                          // same shape as "birth" above
      "date": "1990-01-15", "time": "14:30:00",
      "time_accuracy": "exact", "place_label": "New York"
    },
    "include_composite": true,                            // midpoint chart, default true
    "house_overlay": true                                 // default true
  },

  "include_chinese_astrology": true                       // optional; year pillar only (v1)
}
```

Minimal request: just `birth.date`, `birth.time`, and a known city. Every
other block is opt-in.

### Response (chart packet)

Top-level keys: `meta`, `validation`, `birth`, `settings`, `natal`,
`transits`, `progressions`, `forecast`, `solar_return`, `synastry`,
`chinese_astrology`, `warnings`. Each optional block is `null` if not requested.

- **`validation.validated_for_interpretation`** — the single gate the GPT
  checks before saying anything. `natal_validated` / `transits_validated` /
  `forecast_validated` / `solar_return_validated` / `synastry_validated` /
  `progressions_validated` / `chinese_astrology_validated` each have a sub-flag,
  with `reasons[]` populated whenever something requested didn't complete.
- **`natal`** — `chart_ruler`, `planets[]` (lon, sign, deg_in_sign, speed,
  retrograde, house), `angles{asc,mc}`, `houses[]` (12 cusps), `aspects[]`
  (own internal aspects, with orb/strength/score/applying), `element_balance`,
  `modality_balance`, `lunar_phase`, `retrogrades[]`.
- **`transits`** — `moment_utc`, `orb_policy`, `planets[]`,
  `aspects_to_natal[]` (tight, body-scaled orbs; applying/separating).
- **`progressions`** — `secondary` (day-for-a-year, full chart-shaped output
  including its own houses) and `solar_arc` (every natal point shifted by the
  progressed Sun's arc; directed positions only, no houses of their own).
  Both carry `aspects_to_natal[]`. Uses the conventional fast method for
  progressed angles (progressed JD through natal coordinates), not "real"
  progressed GMT — noted in `warnings` whenever requested.
- **`forecast`** — `mover_hits[]` (exact transit-to-natal hits, Jupiter
  through Pluto only — Moon/Sun/Mercury/Venus/Mars excluded by design),
  `stations[]` (retrograde/direct stations), `eclipses[]` (solar + lunar,
  global — visibility doesn't matter, the degree does), all chronologically
  sorted over the requested window.
- **`solar_return`** — full natal-shaped chart for the year's exact Sun-return
  moment, at the natal location by default or a relocated one on request,
  plus `aspects_to_natal[]` against the primary chart. Flat 3° orb
  (`orb_used`), since a solar return point doesn't "apply" the way a transit
  does.
- **`synastry`** — `partner` (the partner's full natal-shaped chart, same
  shape as top-level `natal`), `cross_aspects[]` (every primary-point ×
  partner-point aspect, labeled `primary`/`partner`, same orb/score formula
  as natal aspects), `house_overlay` (both directions: whose planets fall in
  whose houses — `null` if not requested), `composite` (midpoint method:
  every planet, the two angles, and all 12 house cusps each independently
  midpointed along the shorter arc — explicitly **not** Davison, no synthetic
  time or place is invented; `null` if not requested).
- **`chinese_astrology`** — optional deterministic Chinese zodiac / BaZi-style
  year pillar (`year_pillar.stem`, `year_pillar.branch`, `combined.characters`),
  element and yin/yang tallies for the year pillar only, and `warnings[]`.
  No interpretive text. `null` if not requested.
- **`meta`** — `calc_version`, `settings_version`, `ephemeris`,
  `tzdata_version`, `generated_at`, `input_hash` (cache key — same input +
  versions → same packet).

### Orb conventions (for future reference, not enforced anywhere centrally)

- **Transit → natal**: tight, body-scaled (`transits.TRANSIT_ORB`, ~1-1.5°) —
  these aspects "apply" with real angular motion.
- **Natal internal, synastry cross-aspects, composite internal**: wider,
  body-scaled (`settings.ORB_BY_BODY`, ~3-8°), formula
  `max(orb_a, orb_b) * ASPECT_FACTOR[aspect]` — same formula reused
  identically in all three contexts via `aspects._orb`.
- **Eclipses**: flat 5° (`forecast.ECLIPSE_ORB`) — an eclipse point doesn't
  "apply," so body-scaling doesn't apply either.
- **Solar return → natal**: flat 3° (`solar_return.SR_ORB`) — same reasoning.

## Optional Chinese Astrology Layer

Set `"include_chinese_astrology": true` on the chart-packet request to add a
deterministic symbolic layer alongside the Western chart. Astraeus computes and
structures the data only — no LLM calls, no interpretive meanings, no lucky
colors/numbers/compatibility tables.

**v1 scope:** year pillar only (Heavenly Stem + Earthly Branch), derived from
the Gregorian birth year using 1984 = Jia Zi (甲子) as the reference cycle.
`five_elements_presence` and `yin_yang_presence` count stem + branch of the
year pillar only.

**Calendar boundary:** Chinese New Year and Li Chun are **not** implemented yet.
The block always includes a warning that the year is approximated from the
Gregorian calendar date. This warning does **not** block
`validated_for_interpretation`.

**Future:** full BaZi Four Pillars (year, month, day, hour) can be added as a
separate upgrade without changing existing natal/transit/progression/synastry
logic.

## Geo

`app/core/geo.py` is a small static city → (lat, lon, IANA tz) table
(Belgrade default, plus regional + a few international cities). No live
geocoder, so the calc stays deterministic. Used for primary birth, solar
return relocation, and synastry partner location alike. Add a city by
appending one line, or pass explicit `latitude`/`longitude`/`timezone` to
skip the table entirely.

## Deploy

Dockerized → Google Cloud Run (prod) or Render (simplest). `.se1` files are
baked into the image. Not Vercel (native binary + data files + read-only FS).

```powershell
docker build -t astraeus-calc .
docker run -p 8000:8000 astraeus-calc
```

## Licensing

Swiss Ephemeris is AGPL-3.0 **or** a paid Astrodienst professional license.
**Private/personal use → AGPL is fine.** If this ever becomes public or
commercial, either open-source the service or buy the professional license.
(Not legal advice — verify with Astrodienst.)

## Layout
app/

main.py            FastAPI app + endpoints (incl. GET / for the UI)

schemas.py         request models (BirthIn/SettingsIn/TransitIn/

ProgressionsIn/ForecastIn/SolarReturnIn/SynastryIn)

static/

ui.html           local control panel (single file, no build step)

core/

config.py         ephemeris path/mode detection, auth

geo.py             static city table

timeutil.py        local -> UTC -> Julian Day, add_months, jd_to_utc_iso

ephemeris.py        Swiss Ephemeris wrapper (thread-safe)

aspects.py          natal aspect detection (orb/strength/score formulas

reused by transits/progressions/synastry/composite)

analysis.py          houses/balances/ruler/lunar phase

transits.py           transit snapshot + exact-hit/station root-finding

progressions.py        secondary progressions + solar arc directions

forecast.py             Phase 3: mover hits + stations + eclipses scanner

solar_return.py          Phase 4: solar return chart + aspects_to_natal

synastry.py               Phase 4: cross-aspects, house overlay, composite

validate.py                validation flags (every block independently

hard-gated)

packet.py                  orchestrator; _full_chart() is the shared

bodies/houses/angles/aspects/balance/phase

computation reused by natal, solar return,

and the synastry partner

ephe/                .se1 data files

scripts/

fetch_ephe.py        downloads .se1 files

print_chart.py        CLI: natal chart only

daily_transits.py      CLI: transit snapshot

forecast_scan.py        CLI: forecast scan

solar_return.py          CLI: solar return

tests/               golden-master + property tests per module, all run

against the real Swiss Ephemeris files

## Interpretation workflow (manual, no LLM API calls)

There is no automated LLM call in this repo's actual usage. The real
workflow: generate a packet via the UI or `POST /v1/chart-packet`, copy the
JSON, paste it into a custom GPT (built separately, outside this repo) that
holds the interpretation instructions. This is a deliberate choice to avoid
LLM API token costs — Astraeus only ever computes; it never calls out to an
LLM itself.

`agent/` exists in the repo (an earlier scaffold for an automated
calc → validate → LLM pipeline) but is **not used** and should be treated as
dead code unless that constraint changes. Don't wire it up without an
explicit decision to start paying for LLM API calls.
