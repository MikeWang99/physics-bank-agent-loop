# Physics Bank Web Publisher v1.1.0 — Answer-safe publication

- Removed fabricated `Official answer: A.` from web `practiceStep.solution` when the source only supplies the correct option
- Publish genuine source-derived explanation text only when present
- Preserve full `physicsBank.answer` (source, extraction review, exclusions, ordered worked-answer blocks) under immutable version metadata
- Upload `role=answer` solution figures as content-addressed, version-bound assets; first uses `solutionImage`, later assets remain `answerAssets`
- Hard block unsupported interleaved/multi-figure answer layouts by default; explicit `rendering.allow_answer_layout_degradation` is required to proceed with degraded UI
- Added publish-bundle validation of answer asset roles/slots and regressions
- Existing question, version and storage schema remain unchanged; no production mutations
