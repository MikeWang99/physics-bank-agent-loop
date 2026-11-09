# Changelog

## 3.0.0-rc.5 — 2026-11-09 (learner-facing fidelity gate)

- Carries the source-figure, missing-image, and unsupported-assumption fidelity gate into the standalone Physics Bank source skill and strict validator.
- Preserves verified chapter-wide instructions as provenance; a shared condition that applies to a question must be expressed naturally instead of copied verbatim as a repeated bracketed heading.
- Adds regression coverage for Giancoli-style figure references, editorial figure descriptions, unsupported friction assumptions, and verified shared instructions.
- The separate Web Publisher remains at 1.2.0-rc.2 because this release does not change publishing behavior. No website deployment or production question data is changed.

## 3.0.0-rc.4 — 2026-11-06 (verified section-wide instructions)

- Correct false positives from rc.3 when a physical condition is stated once in an original textbook section heading rather than repeated in every numbered question.
- Preserve exact source-page heading and instruction evidence in reviewed `extraction.shared_source_instructions`; accept them only with verified positive page number and heading text, never from unreviewed generated metadata.
- Add Giancoli GE §4-7 p. 102 (PDF p. 123) regression: `[Ignore friction.]` really is present as a shared instruction for Questions 20–34; avoid labeling it an AI hallucination. Keep it as a real physical assumption in standalone problem context.
- Existing original figure-reference, missing owned figure and unverified assumption hard gates remain.

## 3.0.0-rc.3 — 2026-11-06 (source fidelity hardening)

- Prevent source textbook diagram numbers (e.g. Fig. 4–58), PDF/printed page citations and "Source figure description" editor notes from leaking into learner-facing question stems.
- Reject source-referenced figures with no question-owned reviewed stem/shared figure asset, even when an overlapping source graphic is difficult to crop; quarantine for source review rather than accepting a text-only replacement.
- Detect unsupported "Ignore friction", "Neglect air resistance", and related added physical assumptions when source transcriptions do not explicitly contain the qualifier.
- Add independent Creator/Reviewer source-fidelity rules and focused validator regression tests (Giancoli-like Figure and friction examples).
- Does not rewrite original source PDFs, change TIMBAD scoring, alter published banks or touch website storage. Repairs to previously published questions require separate audited question-version updates.

## 3.0.0-rc.2 — 2026-11-06 (feature branch, NOT production)

- Requires separate live verification of Practice course-subtopic placement and
  unified Topic Practice primary-knowledge-UID placement after publication.
- Records PASS, FAIL, or BLOCKED_AUTH per route; authentication or entitlement
  gaps remain unverified and cannot be reported as successful placement.
- Updates the Web Publisher candidate to 1.2.0-rc.2. No website schema,
  permissions, or production data are changed by this documentation update.

## 3.0.0-rc.1 — 2026-10-26 (feature branch, NOT production)

- Based on main 6338dbb3d7000b1fa3b3842825374de5e4de298f with VERSION=2.9.0;
  Git tag v2.9.0 was not present at audit time.
- Adds classification schema v2, one canonical primary knowledge UID and explicit
  source_system / source_event. Optional new source year, no mandatory year tag.
- Pins 936 website nodes by website commit/Git blob identity and provides
  verified source sync + candidate lookup, strict independent-review audit gates.
- Keeps entire TIMBAD L1-L7 validator and six dimensions unmodified.
- Keeps extraction/answer/visual/PDF source verification and original question IDs.
- Existing v1 semantic classifier, tags and bank taxonomy remain valid for old banks.
- Publisher candidate v1.2.0-rc.1 carries source+UID, keeps full audit metadata,
  refuses unreviewed/missing UID and retains immutable version logic.
- Companion website development PR required before launch. No production writes.
- Accuracy still requires educator-labeled Gold Standard evaluation; no numeric
  classification accuracy claimed. See references/knowledge-classification-v2.md.

