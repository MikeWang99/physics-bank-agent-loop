# Narrative image placement contract · v2.3

The question bank must preserve not only **which visual assets belong to a question**, but also **where each stem/shared figure appears in the source narrative**.

This contract is intentionally compatible with `homework-pdf`, whose renderer already treats `question.layout_blocks` as the authoritative text/figure order.

## Two different kinds of position

### 1. Physical source position → `assets.json`

Each final `stem` / `shared` asset records where the semantic figure came from in the source PDF:

```json
{
  "id": "ap2-q046-bar-chart",
  "file": "assets/figures/ap2-q046-bar-chart.png",
  "role": "stem",
  "owners": ["ap2-q046"],
  "source": {
    "file": "assets/source/ap2-unit9.pdf",
    "page": 12,
    "bbox": [82.4, 211.8, 424.3, 351.6]
  },
  "reviewed": true
}
```

`source.bbox` is `[x0, y0, x1, y1]` in source-PDF points, top-left page coordinate convention as exposed by PyMuPDF page geometry. It identifies the semantic source region; later PNG autotrimming does not change this provenance box.

### 2. Narrative position → `questions.json`

Use ordered `layout_blocks` to reconstruct the source reading order:

```json
{
  "id": "ap2-q046",
  "context": "",
  "stem": "FULL TEXTUAL NARRATIVE OF THE QUESTION",
  "asset_ids": [
    "ap2-q046-pv-main",
    "ap2-q046-bar-chart",
    "ap2-q046-energy-diagram",
    "ap2-q046-pv-final"
  ],
  "layout_blocks": [
    {
      "type": "figure",
      "asset_id": "ap2-q046-pv-main",
      "source_anchor": {"relation": "question_start"}
    },
    {
      "type": "figure",
      "asset_id": "ap2-q046-bar-chart",
      "source_anchor": {
        "relation": "before",
        "text": "A student draws a correct bar chart"
      }
    },
    {
      "type": "text",
      "text": "A student draws a correct bar chart ..."
    },
    {
      "type": "figure",
      "asset_id": "ap2-q046-energy-diagram",
      "source_anchor": {
        "relation": "before",
        "text": "The student also draws a diagram to show the direction"
      }
    },
    {
      "type": "text",
      "text": "The student also draws a diagram to show the direction ..."
    },
    {
      "type": "figure",
      "asset_id": "ap2-q046-pv-final",
      "source_anchor": {
        "relation": "before",
        "text": "A sample of the gas taken from the state"
      }
    },
    {
      "type": "text",
      "text": "A sample of the gas taken from the state ..."
    }
  ],
  "layout_review": {
    "reviewed": true,
    "method": "source-page-visual",
    "reviewed_against_pages": [12, 13]
  }
}
```

The example text is schematic; final bank text must remain source-faithful.

## When layout_blocks are required

For v2.3 strict publication:

- every question with at least one `stem` or `shared` visual asset must have explicit `layout_blocks`;
- every stem/shared asset must appear exactly once as a figure block;
- choice assets remain bound through `choices[].asset_ids` and do not belong in narrative `layout_blocks`;
- text blocks, when concatenated in order, must preserve the question's complete `context + stem` text;
- every figure block must have a `source_anchor`;
- the question must have `layout_review.reviewed: true`.

This is deliberately stronger than the homework renderer's legacy fallback. The bank is the source of truth, so it should never force a downstream renderer to guess image placement.

## source_anchor

Allowed forms:

```json
{"relation": "question_start"}
{"relation": "question_end"}
{"relation": "before", "text": "A student draws a correct bar chart"}
{"relation": "after", "text": "The gas expands at constant pressure"}
```

For `before` / `after`, the anchor text must occur in the textual narrative. Use a short stable source phrase, not a paraphrase.

`source_anchor` is an audit/QA aid. The actual render order is always the array order of `layout_blocks`.

## Review workflow

1. Extract line text and line bboxes into `raw_pages.json`.
2. Discover/crop visual candidates.
3. Record each final visual's source page and semantic `source.bbox`.
4. Reconstruct the full text/figure reading order from the rendered source page.
5. Write `layout_blocks` and `source_anchor` values.
6. Render/inspect the source page side-by-side with the reconstructed order.
7. Only then set `layout_review.reviewed: true`.

If the correct placement cannot be established confidently, keep the question in manual review.
