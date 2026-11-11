# Changelog

## 1.3.1 — 2026-11-11

- Fixes partial-batch delivery positions so accepted questions compile to a contiguous runtime order after quarantined items are removed.
- Keeps original exam question numbers in learner-facing titles while runtime positions are compacted.

## 1.3.0 — 2026-11-11

- Replaces exhaustive post-publish per-question/per-UID checks with a publisher receipt, set-level count check, and one representative smoke check for each requested surface.
- Keeps per-question online checks as targeted diagnostics for observed mismatches, route failures, reported items, or explicit exhaustive-audit requests.
- Clarifies that a surface `PASS` means aggregate release evidence plus a representative route check, not a second live content review.

## 1.2.0 — 2026-11-09

- Releases the learner-facing source audit as a required Creator → Reviewer acceptance gate, including exact prompt/figure inspection and explicit handling of source figure IDs, editorial descriptions, and missing assets.
- Requires shared chapter conditions to have verified source-page and scope evidence, preserves applicable physics assumptions, and rejects copying bracketed section labels verbatim into each learner prompt.
- Synchronizes the bundled Physics Bank snapshot to `3.0.0-rc.5`. The separate Web Publisher remains at `1.2.0-rc.2`; no website deployment or production question data is changed.

## 1.1.1 — 2026-11-06

- Adds a required dual-surface completion gate for live Practice and Topic Practice publication checks.
- Records independent route results and leaves authentication-gated placement unverified until checked in an entitled session.
- Updates the bundled Physics Bank snapshot to 3.0.0-rc.2 and Publisher to 1.2.0-rc.2.

