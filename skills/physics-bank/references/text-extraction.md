# Text extraction contract · v2.6

`physics-bank` v2 separates **faithful extraction** from **semantic enrichment**.

## Stage A: source-faithful extraction

Run `scripts/extract_question_text.py` before asking the model to rewrite or enrich anything. It creates:

- `extraction/raw_pages.json`: line-level page text with bounding boxes. These bboxes are also the primary evidence for reconstructing text/figure reading order in v2.3.
- `extraction/question_drafts.json`: deterministic question boundaries, source pages, raw source text, shared-context candidates, choice candidates, coverage, and review flags.

Never replace `raw_source_text` with a paraphrase. If the PDF text layer is missing or corrupted, leave `requires_manual_review: true`; visually transcribe the rendered source page and record `extraction.method: "visual-transcription"` plus `extraction.text_reviewed: true` only after comparing against the page image.

## Completeness rules

A final question must be self-contained. Copy shared textual stimuli into each final question's `context` while preserving a shared-context ID for provenance. Record every page touched by a question in `source_pages`; a question may span pages. Do not discard continuation text merely because it appears before the next numbered anchor.

Before publishing, compare the final question against `raw_source_text`/page render and set `extraction.text_reviewed: true`. Stage A may preserve flattened math exactly as extracted; Stage B is responsible for converting visually confirmed mathematical typography into canonical `$...$` / `$$...$$` notation without changing the source meaning. Any uncertain symbol, missing line, ambiguous choice label, scan-only page, suspected truncation, or uncertain image placement remains `requires_manual_review: true` until resolved.

For questions with stem/shared visuals, Stage A line bboxes and asset source bboxes must be used together to reconstruct `layout_blocks`. Do not flatten interleaved source prose and figures into "all text first, all images later".

### Published learner text is not a textbook page citation

The audit trail keeps the unchanged source statement, including `Fig. 4–58` and the printed page. The reusable learner's `context`/`stem` must **not** contain original numbered figure references, `See Fig...`, `Source figure description`, or PDF/printed page citations. Link that problem's own reviewed figure in the layout instead, without losing any numerical/physical condition. If the original figure cannot be faithfully isolated, quarantine the question for manual review rather than inventing a narrative stand-in.

No physics assumptions may be introduced merely to make a solvable classroom exercise. An added `[Ignore friction.]`, `Neglect air resistance`, or “frictionless” condition requires explicit wording or a genuinely shared instruction in the source, recorded with page provenance. The reviewer checks the source's *actual* conditions, not what would be convenient for a solution.

## Hard gate

Run:

```bash
python scripts/validate_bank.py question-bank/questions.json \
  --assets question-bank/assets.json \
  --strict --require-text-review
```

A final bank is not publishable until this exits 0.
