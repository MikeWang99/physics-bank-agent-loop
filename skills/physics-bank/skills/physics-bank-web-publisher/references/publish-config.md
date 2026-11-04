# Publish config · pocket-cosmos-publish-config/v1

Example:

```json
{
  "schema": "pocket-cosmos-publish-config/v1",
  "practice_set": {
    "id": "fma-competition-bank",
    "system": "competition",
    "category": "mechanics",
    "practice_kind": "mcq",
    "chapter": 1,
    "chapter_title": "Mechanics",
    "label": "F=ma Competition",
    "title": "F=ma Competition Question Bank",
    "eyebrow": "F=ma",
    "description": "Source-faithful F=ma practice bank",
    "sources": [
      {"label": "F=ma source papers", "url": ""}
    ]
  },
  "rendering": {
    "allow_layout_degradation": false,
    "allow_answer_layout_degradation": false,
    "choice_layout": "stacked"
  },
  "storage": {
    "bucket": "question-assets",
    "prefix": "banks/production/assets"
  },
  "answers": {
    "missing_mcq_nudge": "Select an option to record your response. The source bank does not include an answer key yet."
  }
}
```

## practice_set.system

Current Pocket Cosmos accepted systems include:

- `ap-physics-1`
- `ap-physics-2`
- `ap-c-mech`
- `ap-c-em`
- `igcse`
- `competition`
- `bpho`
- `a-level`
- `physics-bowl`

## practice_kind

Use:

- `mcq` when the set is primarily multiple-choice
- `structured` for FRQ/structured-response sets

The compiler still derives each step mode from whether the individual question has choices.

## Access is deliberately not part of this config

Publishing content does not grant students access and does not change practice permissions. Access remains a separate site/admin concern.

## Layout degradation

Keep `allow_layout_degradation=false` unless the user explicitly accepts the current frontend limitation.

Setting it to true does not remove the original layout. The complete `layoutBlocks` remains under `metadata.physicsBank`, and the compiled question is marked degraded.

## Worked-answer layout

`rendering.allow_answer_layout_degradation` defaults to false. With the current UI, worked answers containing multiple figures or a figure before additional prose cannot be faithfully displayed; block rather than silently reorder. The raw answer and every figure remain preserved under `metadata.physicsBank.answer` and version-bound answer assets. Never automatically opt into degradation.
