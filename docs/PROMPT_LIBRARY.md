# Astraeus Prompt Library

`/prompts` is the first user-facing prompt-template release.

## Scope

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

Every template has three audience levels (`beginner`, `intermediate`, `expert`) and three depth levels (`concise`, `detailed`, `exhaustive`). Audience level changes language, not the evidence set.

## Stage-3 contract

Generated prompts explicitly enforce `qualified_birth_time_v1` rules:
- `value` is interpreter-facing only when non-null;
- `nominal` is not promoted to fact when unresolved;
- `possible_values` are alternatives;
- `nominal_orb` is not reconstructed into a resolved orb;
- `audit_only_nominal` and `birth_time_sensitive_nominal_*` are excluded from ordinary interpretation;
- suppressed synastry overlay/composite geometry is not rebuilt.

## Prediction boundary

This release intentionally has no `current period`, `specific date`, or `30/90/365 day` forecast templates. Solar Return and progressions templates interpret already-calculated symbolic structures but may not produce concrete outcome predictions. Prediction templates belong to the later Context Builder + Prediction Audit release.

## Packet handoff

The calculator stores the last successful packet in browser `localStorage` under `astraeus-last-packet`. `/prompts` can copy either the prompt alone or `prompt + current packet`. The page does not upload the saved packet to a new server endpoint.
