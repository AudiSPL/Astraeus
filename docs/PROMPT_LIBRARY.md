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

Forecast Lab is audit-gated:
1. calculate target + matched control without user context;
2. rank a small context-blind evidence shortlist;
3. freeze the shortlist + hash;
4. add context only after freeze;
5. withhold full forecast arrays from the LLM;
6. save falsifiable claims and review target vs control later.

This keeps prediction workflow separate from the static Prompt Library templates.

## Packet/request handoff

The calculator stores the last successful packet in browser `localStorage` under `astraeus-last-packet` for static Prompt Library use. It also stores the last successful request under `astraeus-last-request` so Forecast Lab can regenerate target/control forecast windows with the same natal/settings input.

No LLM API call is made by either page.
