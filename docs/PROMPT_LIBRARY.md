# Astraeus Prompt Library

`/prompts` contains Stage-3-aware copy/paste interpretation templates.

## Static interpretation templates

Included templates:
- Explain this packet
- Natal analysis
- Synastry
- Composite
- Solar Return
- Progressions + Solar Arc
- BaZi / Four Pillars
- Western + BaZi comparative synthesis
- Full static reading

Every static template has three audience levels (`beginner`, `intermediate`, `expert`) and three depth levels (`concise`, `detailed`, `exhaustive`). Audience level changes language, not the evidence set.

## Task-scoped validation

Prompt Library uses `task_scoped_v1` validation. The aggregate
`validation.validated_for_interpretation` flag is not an unconditional stop when
per-block flags exist. A packet can be aggregate-false because one optional block
(such as synastry with unknown partner birth time) is unresolved while natal,
Solar Return, progressions or BaZi remain individually valid.

Task mapping:
- Natal -> `natal_validated`
- Synastry / Composite -> `synastry_validated` plus suppression metadata
- Solar Return -> `solar_return_validated`
- Progressions / Solar Arc -> `progressions_validated`
- BaZi -> `bazi_validated`
- Western + BaZi -> validate natal and BaZi separately; synthesis requires both
- Full static reading -> interpret valid requested blocks and skip invalid ones
- Explain this packet -> diagnostic; report all available validation statuses even when the aggregate flag is false

If a required per-block flag is missing, templates fall back to the aggregate
flag. Field-level Stage-3 qualification still applies inside every validated
block: validation never makes a null/suppressed/audit-only field usable.

## Stage-3 contract

Generated prompts explicitly enforce `qualified_birth_time_v1` rules:
- `value` is interpreter-facing only when non-null;
- `nominal` is not promoted to fact when unresolved;
- `possible_values` are alternatives;
- `nominal_orb` is not reconstructed into a resolved orb;
- `audit_only_nominal` and `birth_time_sensitive_nominal_*` are excluded from ordinary interpretation;
- suppressed synastry overlay/composite geometry is not rebuilt.

## Forecast boundary after Release 3

The Prompt Library still does **not** generate a direct timeframe forecast from a full packet. Instead it links 30/90/365-day forecast cards to `/forecast-lab`.

Forecast Lab v1.1 is audit-gated:
1. calculate target + same-season matched control without user context;
2. rank a small context-blind evidence shortlist;
3. freeze the shortlist + hash and random A/B mapping;
4. replace real dates with relative Day offsets before the scored LLM package is built;
5. generate blind scored claims using only a minimal broad domain, while detailed life context remains withheld;
6. save the falsifiable claims;
7. only then unlock detailed context for a separate non-scored interpretation that cannot modify the claims;
8. keep full forecast arrays withheld and review target vs control later.

This keeps prediction workflow separate from the static Prompt Library templates.

## Packet/request handoff

The calculator stores the last successful packet in browser `localStorage` under `astraeus-last-packet` for static Prompt Library use. It also stores the last successful request under `astraeus-last-request` so Forecast Lab can regenerate target/control forecast windows with the same natal/settings input.

No LLM API call is made by either page.
