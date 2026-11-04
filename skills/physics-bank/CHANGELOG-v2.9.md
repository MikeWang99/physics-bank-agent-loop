# Physics Bank v2.9.0 — Source-bound answer vision QA

- Builds on v2.8 TIMBAD assessment and existing v2.7 minimal answer extraction; no changes to the question-bank schema version (2.0).
- Adds original-source visual review for newly extracted `worked_solution` answers, including source PNG/JPEG as well as PDFs.
- Adds `render_answer_review_sheet.py` with green instructional diagram boxes and orange proposed signature/watermark omission boxes over the unmodified source.
- Adds `seal_answer_review.py`, requiring explicit text/math/diagram checks and exclusion acknowledgement; records the original answer source hash, page, region bbox and review-sheet hash.
- Strict `validate_bank.py` now verifies source-region review attestations, original SHA, page bounds, answer diagram containment, and rejects excluded marks intersecting retained answer diagrams.
- Focused `validate_answer_content.py` enforces the same source-visual gate (no bypass).
- Keeps key-only answer records minimal and separate from official-source attribution; preserves original image/PDF as audit evidence.
- Adds source tampering, missing/false review, overlapping signatures, out-of-region exclusions, PDF review-sheet sealing and raster-source tests.
- Keeps all answer images and `answer.visual_review` preserved through the existing Web Publisher v1.1 `metadata.physicsBank.answer` contract; no production DB changes.
- Automated geometry/SHA checks do not prove that the model read the source correctly; visual inspection remains required.
