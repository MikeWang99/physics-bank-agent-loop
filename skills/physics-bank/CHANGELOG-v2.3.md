# v2.3.0 — Narrative figure placement

- Added a formal narrative-layout contract compatible with `homework-pdf`'s existing `question.layout_blocks` renderer
- Stem/shared assets now preserve physical source geometry using `source.page + source.bbox`
- Questions with stem/shared visuals must preserve the complete text/figure reading order in `layout_blocks`
- Every narrative figure block carries a source anchor (`before / after / question_start / question_end`)
- Added `layout_review` so image placement cannot be marked complete before visual source comparison
- Strict validation rejects missing layout blocks, omitted/duplicated figures, invalid anchors, missing source bboxes, unreviewed layout, and layout text that drops/reorders source prose
- Choice-image placement remains structurally bound through `choices[].asset_ids`
- Added regression tests for multi-image narrative order and source-geometry requirements
