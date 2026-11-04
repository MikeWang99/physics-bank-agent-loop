# Physics Bank v2.7.0 — Source-faithful answer extraction

- Split answer-key-only records from source-provided worked explanations with optional `answer.kind` (`key_only`, `worked_solution`, `not_provided`)
- A single official option letter is stored in `answer.label`; `answer.text` remains empty, without AAPT/board attribution boilerplate or invented solutions
- Preserve answer citations and the unchanged source document separately under `answer.source` and `answer.extraction`
- Added independently extracted answer illustrations in `assets/answers/<question-id>/` with `role=answer`; both `answer.asset_ids` and top-level question `asset_ids` reference them
- Preserve original worked-answer text/figure order through `answer.layout_blocks` and visually reviewed `answer.layout_review`
- Source PDF/answer image remains untouched; omitted signatures, watermarks and headers require explicit `excluded_non_instructional` kind, bbox and reason, with manual review whenever physics content could be lost
- Extended strict visual review SHA/bbox checks and sealing to answer figures, including answer pages outside `question.source_pages`
- Added focused `validate_answer_content.py`, integrated strict checks in `validate_bank.py`, and math checks for answer layout text
- Added comprehensive regressions for label-only behavior, diagram-based answers, original-source review seals and documented exclusions
- Compatible with older `answer: {label, text, evidence}` records; current schema_version remains 2.0

Companion publisher under `skills/physics-bank-web-publisher` upgraded separately to v1.1.0.
