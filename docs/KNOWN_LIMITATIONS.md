# Known limitations

## Correctness baseline

The validated baseline at `846b98e` reports `327 passed`, `0 xfailed`, with one external Starlette/httpx deprecation warning. The four previously tracked strict-xfail defects were closed in `846b98e`:

1. Circular midpoint longitude is canonicalized to `0 <= lon < 360`.
2. Whole Sign composite cusps are rebuilt on sign boundaries from the composite Ascendant sign.
3. Whole Sign composite H1 is kept consistent with the composite Ascendant sign.
4. Synastry `cross_aspects` no longer exposes applying/separating semantics across different natal epochs.

This does not mean the product is free of defects; it means there are no currently registered expected-failure tests in this baseline.

## Precision and metadata backlog

- Forecast exact-hit calculation still uses scan/refinement rather than a bracketed root solver, and natal target longitudes are quantized to six decimal places. Do not assign meaning to sub-second forecast timing.
- BaZi has remaining ephemeris-mode plumbing debt in the standalone calculation path/metadata.
- Ayanamsha is propagated through the calculation frame, but per-event forecast/eclipse epoch metadata and synastry-partner epoch metadata are not yet equally granular everywhere.

## Product boundary

Prediction Audit is implemented through Forecast Lab v1.1 at `/forecast-lab`. Prompt Library is available at `/prompts`. Forecast Lab v1.1 is available at `/forecast-lab` and uses context-blind evidence selection, date-blinded scored claims, a same-season next-year control window, and detailed context only after scored claims are frozen. The full forecast packet remains withheld from the scored interpreter package. Forecast Lab is an experimental audit workflow, not evidence that astrology has established predictive validity.
