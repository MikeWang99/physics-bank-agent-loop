# v1.0.0 — Pocket Cosmos publisher

- Added a dedicated compiler from validated physics-bank bundles to the current Pocket Cosmos `practiceSet/practiceStep` runtime contract
- Preserves full physics-bank semantic classification, layout blocks, provenance and review metadata under `question_versions.metadata.physicsBank`
- Uses the existing production version model: stable `questions` identity, immutable `question_versions`, and version-bound `question_assets`
- Prepends shared `context` to the displayed stem because the current Practice client renders `prompt` but does not independently render `context`
- Added a hard compatibility gate for narrative layouts that the current prompt→image→supportingImages frontend cannot reproduce
- Added content-addressed immutable Storage paths under `question-assets/banks/<set>/assets/`
- Added plan-first Storage uploader with no overwrite by default
- Added deterministic publish-bundle content hashes that exclude signed URLs, UUIDs and timestamps
- Added one-transaction SQL generator that reuses an existing `question_id + content_hash` version or appends a new immutable version
- Added runtime API verification for question count/order and version linkage
- Publishing intentionally does not alter permissions, assignments, attempts, or historical versions
