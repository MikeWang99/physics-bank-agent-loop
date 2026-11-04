# Visual choice assets · v2.2

Use this contract whenever one or more answer options are diagrams, graphs, circuits, images, or other visual objects.

## Non-negotiable rule

One semantic answer option = one independently reviewable asset (or an explicitly indexed set of assets for that same option).

Do **not** publish a raster containing A+B+C+D together as a final choice asset. Such combined images are acceptable only as temporary discovery/cropping sources.

## Canonical layout

```text
assets/choices/<question-id>/A-01.png
assets/choices/<question-id>/B-01.png
assets/choices/<question-id>/C-01.png
assets/choices/<question-id>/D-01.png
```

The printed option label should normally be excluded from the raster because the label is stored in JSON. Keep it only if removing it would cut meaningful visual content; in that case record the reason in crop metadata.

## QA checklist per option

Before setting `reviewed=true` and `crop.isolated_choice=true`, visually verify:

1. the complete intended option image is present;
2. no pixels from adjacent options are present;
3. axes, arrowheads, endpoints, legends, units, circuit nodes, and labels are intact;
4. no question prose, footer, score, or answer-key material leaked in;
5. the asset's `choice_label` matches the source option;
6. its owner question ID is correct;
7. its final path matches the canonical folder/filename.

If any check fails, re-crop and re-inspect the **final** file.

## JSON binding

```json
{
  "choices": [
    {"label": "A", "text": "", "asset_ids": ["fma-2016-q005-choice-A-01"]}
  ],
  "asset_ids": ["fma-2016-q005-choice-A-01"]
}
```

`choices[].asset_ids` is the precise semantic binding. Top-level `asset_ids` is retained for compatibility with downstream renderers.
