# Astraeus Forecast Lab — audit contract v1.1

Forecast Lab is Astraeus's experimental forward-looking audit surface. Its job is not to make a persuasive narrative. Its job is to freeze a small evidence set before interpretation, generate falsifiable claims under a blinded procedure, and compare a target window with a matched control.

## Ordering guarantee

The v1.1 workflow is intentionally staged:

1. Start from the last successful Calculator request.
2. Calculate the target window and a same-season control without user context.
3. Rank each window using a fixed, context-blind rule.
4. Freeze a small per-technique shortlist and SHA-256 selection hash.
5. Randomly map the two windows to A/B.
6. Convert interpreter-facing timing to relative Day 0…N offsets. Real calendar dates stay local and are withheld from the scored LLM package.
7. Give the scored LLM only a broad domain such as `career` or `money`; detailed life context is still withheld.
8. Save falsifiable blind scored claims using day offsets.
9. Only after the claims are saved, unlock detailed context for a separate non-scored interpretation package. That package may explain relevance but cannot add, delete, edit, widen, narrow or replace scored claims.
10. Review both windows after they end, score each claim, then reveal target/control mapping and compare hit rates.

The hash proves that the interpreter-facing shortlist did not change after freeze. It is not a third-party timestamp attestation.

## Ranker v1.1

`context-blind-forecast-v1.1` keeps the v1 deterministic ranking model and quota separation.

Forecast exact hits are grouped into transit series by `(transit, natal, aspect)` before ranking, so retrograde multi-pass dates do not count as separate independent evidence items.

Per window quotas remain:

- up to 5 transit series;
- up to 2 eclipse events with interpreter-facing natal hits.

Stations are not sent to the scored interpreter. No universal score compares transit-series and eclipses; each technique keeps its own quota.

## Same-season matched control

The control starts on the same calendar month/day in the following year and has the same number of days as the target. If a civil-date edge case would overlap the target, Astraeus advances by whole calendar years until the control is non-overlapping.

This is stronger than v1's fixed 183-day displacement because it reduces obvious seasonal base-rate differences in observable events such as hiring, travel and purchasing. It is still not a complete randomized null model.

A/B labels are randomized and kept in the local audit record. The scored LLM does not receive target/control mapping or real window dates. User blinding is still imperfect because the user selected the target date. LLM blinding is materially stronger but not absolute: a model with outside ephemeris access or memorized astronomical timing could theoretically infer chronology, which is why the prompt also forbids searching or reconstructing withheld factors.

## Day-offset blinding

The scored package uses `forecast_audit_v2` and `forecast_claims_v2`.

Each window is represented as `Day 0` through `Day N`. Transit exact dates become `exact_day_offsets`; eclipse dates become `day_offset`. Scored claims use integer `start_day` and `end_day`.

The browser keeps the real date mapping locally for later scoring. Review maps those offsets back to actual dates only inside the local UI. Calendar dates are therefore not needed by the LLM to create a claim.

## Context separation

The scored phase receives only minimal domain context. It does not receive the user's current situation, goals, past events, deadlines, or phrases such as “now” or “in a few days” that could reveal the target window.

Detailed context is unlocked only after the scored claims are saved. It is used for a separate non-scored interpretation. The post-claim prompt explicitly forbids changing the frozen claims or generating new scored predictions.

This separation is deliberate: context can help explanation, but it must not be allowed to choose the evidence or retrofit the scored prediction.

## Scorable claims

A scored claim must be externally observable, bounded within the blind window, and traceable to frozen evidence. It requires:

- event type;
- observable event text;
- verification rule;
- integer `start_day` / `end_day` inside the window;
- one or more frozen evidence IDs from that same window.

Vague themes such as opportunity, visibility, pressure, transformation, mood or “important energy” can appear only in prose, not in `forecast_claims`.

Astraeus does not assign calibrated probabilities.

Health diagnosis/treatment claims and investment-return guarantees are excluded. Legal outcomes are also excluded from scoring. The exclusion covers verdicts, judgments, win/loss, settlements, settlement agreements, damages, awards, compensation, severance, back pay and other legal-dispute-related payments. Ordinary non-legal contracts and ordinary purchases/payments can still be scored if they are objectively observable.

## Storage and compatibility

Forecast Lab remains browser-local. Source request, freeze snapshots, claims, pasted LLM response and ratings are stored in browser `localStorage`. No server-side personal-context database or LLM API key is added.

v1.1 creates a new freeze key so an unfinished v1 freeze is not silently treated as a v1.1 freeze. Saved audit storage remains compatible with existing v1 audit records, and Import accepts both v1 and v2 export envelopes.

## What this audit can and cannot show

A target-vs-control difference across many preregistered audits can be evidence worth investigating. A single successful reading is not validation. A tie or control-window win is informative and should not be reinterpreted away.

The audit remains an experimental methodology. The main improvement in v1.1 is not a new astrology technique; it is stricter information separation between calculation, blinded claims, detailed context and outcome review.
