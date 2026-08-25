# Astraeus Forecast Lab — audit contract v1.2

Forecast Lab is Astraeus's experimental forward-looking audit surface. Its purpose is not to produce the most persuasive narrative. Its purpose is to freeze a small evidence set before interpretation, define falsifiable claims under an information-control procedure, and compare a target window with a matched control.

## What changed in v1.2

v1.2 hardens four weaknesses exposed by practical testing of v1.1:

1. **Paired evidence counts.** Candidate ranking still uses separate technique quotas, but the interpreter-facing shortlist is trimmed so Window A and Window B receive the same number of transit-series slots and the same number of eclipse slots. Different rank scores are retained; evidence counts are the controlled quantity.
2. **Verified freeze checksum.** Astraeus recomputes the SHA-256 hash from the stored interpreter-facing frozen shortlist before accepting claims. It also hashes the structured claims after validation and rechecks both hashes before reveal/import actions. The hash is an integrity checksum, not authentication, a trusted timestamp, or cryptographic proof against a user who can edit browser storage and recompute hashes.
3. **Fixed claim slots.** Each window has exactly two `claim_slots`. A slot is either `kind: "claim"` or `kind: "no_claim"`. Equal slot count no longer forces equal numbers of positive predictions and never requires filler claims.
4. **Sealed Self-Audit mode.** A participant testing predictions on themself can keep claim content hidden until both windows have ended and an outcome log for both windows has been frozen first. This mode requires an external operator or another opaque file handoff; Astraeus cannot make a manually opened LLM conversation invisible to the person reading it.

## Ordering guarantee

The v1.2 workflow is staged:

1. Start from the last successful Calculator request.
2. Calculate target and same-season control without detailed user context.
3. Rank each window with the deterministic context-blind ranker.
4. Take up to the candidate quotas per technique, then pair the **counts** by technique using the smaller available count across A/B.
5. Randomly map the two real windows to A/B.
6. Convert interpreter-facing timing to Day 0…N offsets. Calendar dates remain local.
7. Freeze the paired shortlist and compute `selection_hash`.
8. Before claims are accepted, recompute that hash from the stored shortlist and reject a mismatch.
9. Give the scored LLM only the frozen evidence and a broad domain.
10. Require exactly two claim slots per window. A slot may explicitly be `no_claim` when evidence does not support a falsifiable event.
11. Hash the validated structured claims as `claims_hash`.
12. In Open exploratory mode, claims may be displayed and detailed context may be added afterward for a non-scored interpretation.
13. In Sealed Self-Audit mode, claim content and detailed context remain hidden/locked until both real windows end. The participant first records and freezes objective outcome logs for A and B. Only then may claims be revealed and scored.
14. Target/control mapping is revealed only after all positive claim slots have an outcome rating.

## Ranker v1.2

`context-blind-forecast-v1.2` keeps the same basic deterministic body/natal/aspect weighting model used by v1.1. Exact hits are grouped into transit series by `(transit, natal, aspect)` before ranking, so retrograde multi-pass dates are not counted as separate evidence items.

Candidate caps remain:

- up to 5 transit series per real window;
- up to 2 eclipse events per real window.

After ranking, Astraeus computes `paired_quotas` independently for each technique:

`paired_count(technique) = min(candidate_count_A, candidate_count_B, candidate_cap)`

Both A and B are then trimmed to that count. This removes evidence-count asymmetry as a procedural confound without pretending that transit and eclipse rank scores share one meaningful universal scale.

## Same-season matched control

The control starts on the same calendar month/day in the following year and has the same number of days as the target. If necessary to avoid overlap, the control advances by whole calendar years.

This reduces obvious seasonal base-rate differences relative to the old fixed 183-day displacement. It is not a randomized null model, and the participant may still know which real period they originally selected.

## Date blinding and sealed subject mode

The scored package uses `forecast_audit_v3` and `forecast_claims_v3`. Real dates become day offsets before the package is copied or exported.

In default Sealed Self-Audit mode, Astraeus also hides the local evidence names and exact hit dates from the participant-facing evidence panel. The blind prompt may be exported to an external operator. The returned claims file is imported without showing claim text in the Astraeus UI.

This only works as intended if the participant does **not** open or read the external LLM response. If the same person reads the response before import, the seal has been broken. Use Open exploratory mode instead of pretending that run remained blind.

## Fixed claim slots

Every A/B window must contain exactly two slots:

```json
{
  "slot_id": "A-S1",
  "kind": "claim",
  "claim_id": "A-C1",
  "start_day": 10,
  "end_day": 20,
  "event_type": "job_interview",
  "observable_event": "At least one concrete job interview occurs.",
  "verification_rule": "YES only if an interview with a real employer is scheduled or completed.",
  "evidence_ids": ["A-T1"]
}
```

or:

```json
{
  "slot_id": "A-S2",
  "kind": "no_claim",
  "reason": "Frozen evidence does not justify a second falsifiable external event."
}
```

A `no_claim` slot is not a miss and is not part of the hit-rate denominator. It exists so the two windows have equal structural opportunity without forcing fabricated predictions.

## Claim restrictions

Positive claims must be externally observable, bounded by integer `start_day` / `end_day`, traceable to evidence IDs from the same window, and paired with a verification rule. Vague themes such as pressure, opportunity, visibility, transformation, mood, or “important energy” stay outside scoring.

Astraeus does not assign calibrated probabilities.

Health diagnosis/treatment claims, investment-return guarantees, and legal-dispute outcomes are excluded. Legal exclusion includes verdicts, win/loss, settlements, settlement agreements, damages, awards, compensation, severance, back pay, and payments arising from litigation or an employment dispute.

## Hash verification

`selection_hash` is created from the interpreter-facing frozen payload before claims are generated. Before claim save/import, Astraeus rebuilds that payload from its stored freeze and recomputes the SHA-256 value. A mismatch is rejected.

After structured claims pass schema validation, Astraeus creates `claims_hash`. New v1.2 audits recheck both freeze integrity and claims integrity before sealed reveal and before target/control reveal. New v3 audit exports are verified on import.

This catches accidental or unsynchronized modification of the browser-local audit record. It does **not** provide server-backed immutability or third-party attestation.

## Outcome-first sealed review

For `sealed_self_v1`, the participant cannot see claims or create a detailed context interpretation while either window is still live. After both windows end, the UI asks for one objective outcome log per window. Both logs are hashed and frozen before the claim text can be unlocked.

Only after that sequence may the user:

1. reveal sealed claim content;
2. rate positive claim slots as `Occurred`, `Did not occur`, or `Not assessable`;
3. reveal target/control mapping after all ratings are complete.

This reduces the risk that reading the prediction changes behavior or causes the participant to write the outcome record around remembered claim wording. It does not remove self-report bias; an independent scorer remains stronger.

## Open exploratory mode

`open_exploratory_v1` preserves the convenient v1.1 workflow: the user may paste and read claims immediately, then add detailed non-scored context. It is useful for product testing and interpretation experiments but must not be described as a blinded self-audit.

## Storage and compatibility

Forecast Lab remains browser-local. No LLM API key or personal-context backend is introduced.

v1.2 uses a new freeze key, `astraeus-forecast-freeze-v3`, so unfinished v1.1 freezes are not silently reinterpreted under the new methodology. Audit storage keeps the existing browser key for continuity. Export envelope v3 is produced; imports accept v1, v2, and v3 envelopes. New v3 audits are integrity-checked during import, while legacy records remain legacy/unverified methodology.

## What the audit can and cannot show

A preregistered target-vs-control difference across many runs can be evidence worth investigating. A single apparent hit is not validation. A tie, no-claim result, or control-window win must remain in the record rather than being explained away.

Forecast Lab v1.2 improves information control and auditability. It does not establish that astrology predicts real-world events.
