# Astraeus Forecast Lab — audit contract v1

Forecast Lab is the first Astraeus feature that combines forward-looking calculation, user context and an outcome review loop.

## Ordering guarantee

The workflow is intentionally staged:

1. Start from the last successful Calculator request.
2. Calculate two forecast windows without user context.
3. Rank each window using a fixed, context-blind rule.
4. Freeze a small per-technique shortlist and SHA-256 hash.
5. Only then unlock the Context Builder.
6. Copy only the frozen evidence + context to the LLM. The full forecast packet is withheld.
7. Paste back only falsifiable scored claims.
8. Review both windows after they end, then reveal target/control mapping and compare hit rates.

The hash proves that the frozen shortlist has not changed after creation; it is not a cryptographic attestation from a third-party timestamp authority.

## Ranker v1

`context-blind-forecast-v1` reuses the same deterministic body/natal/aspect weights used by Astraeus transit ranking.

Forecast exact hits are grouped into transit series by `(transit, natal, aspect)` before ranking, so retrograde multi-pass dates do not count as separate independent evidence items.

Per window quotas:

- up to 5 transit series
- up to 2 eclipse events with interpreter-facing natal hits

Stations are not sent to the interpreter in v1. No universal score compares transit-series and eclipses; quotas keep techniques separate.

## Control window

The control window has the same length as the target window and begins 183 days after the target window ends. This avoids overlap even for long horizons. It is a simple temporal-displacement control, not a complete randomized null model.

A/B labels are randomized before context is entered. This blinding is strongest for the LLM: the copied package does not identify target/control. User blinding is imperfect because the user originally selected the target dates and could infer them. The local audit record keeps the hidden map and the normal UI does not reveal it until both windows are reviewable and all scored claims have a rating.

## Scorable claims

Scored claims must be externally observable and bounded in time. They require:

- event type
- observable event text
- verification rule
- start/end dates inside the window
- one or more frozen evidence IDs from the same window

Vague themes such as opportunity, visibility, pressure, transformation or mood are allowed only in prose, not in `forecast_claims`.

Astraeus does not assign calibrated probabilities. Medical diagnosis/treatment claims, legal verdict/win-loss claims and guaranteed investment returns are excluded.

## Storage and privacy

Forecast Lab stores source request, freeze snapshots, pasted LLM response, claims and reviews in browser `localStorage`. It does not create a server-side personal-context database and does not call an LLM API.

Use Export/Import in the Review section if you need to move audit records to another browser/device or protect against local browser-data loss.

## What this audit can and cannot show

A target-vs-control difference across many preregistered audits can be evidence worth investigating. A single successful reading is not validation. A target/control tie is informative and should not be reinterpreted away.

The v1 audit is deliberately simple. Future work may add stronger matched controls, blind third-party scoring and aggregated calibration statistics without changing the basic freeze-before-context rule.
