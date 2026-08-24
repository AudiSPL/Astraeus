# Known limitations

## Current strict xfails

The validated baseline immediately before the Guide release reports 4 expected failures.

1. Whole Sign composite cusp geometry has a known correctness edge case.
2. Whole Sign composite H1 can fall outside the composite ASC sign in a known edge case.
3. Circular midpoint normalization can emit `360.0` instead of a longitude in `0 <= lon < 360`.
4. Synastry `cross_aspects` applying/separating has a latent hazard when different natal epochs are combined.

## Precision and metadata backlog

- Forecast exact-hit calculation still uses scan/refinement rather than a bracketed root solver, and natal target longitudes are quantized to six decimal places. Do not assign meaning to sub-second forecast timing.
- BaZi has remaining ephemeris-mode plumbing debt in the standalone calculation path/metadata.
- Ayanamsha is propagated through the calculation frame, but per-event forecast/eclipse epoch metadata and synastry-partner epoch metadata are not yet equally granular everywhere.

## Product boundary

Prompt Library, Context Builder and Prediction Audit are intentionally outside the Guide release. Timeframe forecast prompt cards should not ship before the audit loop exists.
