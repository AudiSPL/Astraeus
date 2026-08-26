# Astraeus roadmap

This is a planning backlog, not a release promise. Items move into implementation only after their scope and acceptance criteria are explicitly agreed.

## Deferred product work

### English localization

- Add a complete English-language product copy pass for the Astraeus UI and user-facing guidance.
- Use the user's approved copy, to be supplied later from the separate copy-review conversation; do not freeze or auto-translate final wording before that source is provided.
- Keep API keys and deterministic calculation contracts language-neutral unless a separate contract change is intentionally approved.
- Decide whether localization remains a two-language static UI or becomes a reusable locale layer only when implementation starts.

### Mobile JSON handoff

Problem: full Astraeus chart and comparison JSON can become too large or awkward to select, copy and paste reliably on mobile browsers.

Goals and constraints:

- make mobile handoff to ChatGPT/other interpreters reliable without losing deterministic calculation context;
- preserve validation flags, versions, provenance and integrity metadata;
- the product must never silently truncate a packet to make clipboard copying succeed;
- do not replace the canonical full JSON until a smaller handoff contract is proven equivalent for its intended interpretation task.

Design options to evaluate before implementation:

1. download/share the canonical packet as a `.json` file from mobile;
2. add a deterministic compact interpretation packet containing only fields required by the selected task, with an explicit schema/version and linkage to the full packet hash;
3. provide section-based export or chunked copy with an integrity/ordering manifest when a single clipboard operation is unreliable;
4. keep one-click full-copy on desktop while offering a mobile-specific share/file path rather than relying on very large clipboard payloads.

Before choosing an approach, test real iOS/Android browser clipboard and file-share behavior with large natal, forecast, synastry and Birth-Time Comparison packets.

## Existing technical backlog

- Continue metadata/provenance convergence between specialized tools and the canonical Calculator packet without changing calculation results or recapturing goldens merely to satisfy tests.
- Keep future Birth-Time Comparison work separate from rectification unless a rectification method, evidence contract and validation strategy are explicitly designed.
