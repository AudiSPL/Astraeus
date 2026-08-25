# Birth-Time Comparison v1

Birth-Time Comparison is a deterministic comparison tool for multiple candidate birth times on the same birth date. It is not a rectification engine and it does not claim that a candidate is the true birth time.

## Core rule

Each candidate is calculated independently through the normal Astraeus natal calculation pipeline. The comparison output keeps angle, house and angle-aspect geometry attached to the candidate state that produced it.

A consumer must never combine, for example, an Ascendant from candidate T2 with an ASC aspect orb from candidate T1.

## API

`POST /v1/birth-time-comparison`

Request:

```json
{
  "base_request": {
    "birth": {"date": "1984-07-24", "time": "05:10:00", "timezone": "Europe/Belgrade"},
    "settings": {"zodiac": "tropical", "house_system": "whole_sign"}
  },
  "candidate_times": ["05:05", "05:07", "05:10", "05:13", "05:15"]
}
```

Candidate times are normalised to `HH:MM:SS`, deduplicated, sorted within the same birth date and limited to 12 candidates.

The API reuses the normal Calculator `ChartRequest` validation for the natal `birth` and `settings` input before any candidate calculation. Optional modules are deliberately excluded from that validation path because v1 withholds them rather than calculating them.

## Point-evaluation semantics

The source request retains its declared time precision and provenance in the comparison metadata. For calculation only, each candidate is evaluated as an exact point with zero uncertainty. This is a computational assumption for a candidate state, not a rewrite of the source birth record and not evidence that the candidate time is exact.

Optional transit, forecast, progression, solar-return, synastry and BaZi blocks are not copied into candidate requests in v1. The feature is intentionally limited to natal birth-time-sensitive geometry.

## Compared fields

The v1 response includes complete candidate states for:

- ASC and MC longitude/sign;
- chart ruler;
- all 12 house cusps/signs;
- natal planet longitude/sign/house placement;
- natal aspects involving ASC or MC, including candidate-specific orb.

The comparison layer classifies categorical values as stable or changed and emits transition intervals when two adjacent sampled candidates differ.

## Transition interval limitation

A transition interval such as `05:10 -> 05:13` means only that the sampled states differ at those endpoints. v1 does not run a root solver and must not report an exact transition minute or second unless that exact instant was itself calculated as a candidate.

## LLM handoff contract

The UI can build a comparison prompt from the deterministic response. The prompt requires the interpreter to:

1. keep every candidate as one correlated state;
2. never reconstruct missing geometry;
3. never mix geometry across candidates;
4. distinguish stable interpretation claims from candidate-specific claims;
5. treat transition intervals as sample bounds only;
6. avoid choosing a true birth time or presenting the comparison as validated rectification.

## Civil-time limitation

Nonexistent local times already fail in the normal time-resolution pipeline. Birth-Time Comparison v1 also refuses ambiguous local civil times because one wall-clock candidate would otherwise refer to more than one possible instant.

## Integrity

The response contains `comparison_hash`, a SHA-256 digest over the deterministic comparison payload excluding `generated_utc` and the hash field itself. It is an integrity checksum, not third-party timestamping or authentication.
