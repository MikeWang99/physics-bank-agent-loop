# Question-bank schema and asset manifest · v2.9

The compact example below illustrates an **unrated draft**: the question's visual options still need inspection. Use [difficulty-assessment.md](difficulty-assessment.md) for an APPROVED TIMBAD audit; usable levels are L1–L7. This example cannot pass strict publication until review is complete.

Paths are relative to the bundle root. The schema keeps text provenance, source year, visual provenance, and visual-choice ownership explicit.

```json
{
  "schema_version": "2.0",
  "questions": [
    {
      "id": "fma-2016-q005",
      "year": 2016,
      "year_evidence": {"method": "source-four-digit", "value": "assets/source/2016_Fma_exam.pdf"},
      "tags": ["year:2016"],
      "source": {"file": "assets/source/2016_Fma_exam.pdf", "page": 3, "original_number": "5", "year": 2016},
      "source_pages": [3],
      "content_format": "markdown+latex",
      "context": "",
      "stem": "Which graph is correct?",
      "choices": [
        {"label": "A", "text": "", "asset_ids": ["fma-2016-q005-choice-A-01"]},
        {"label": "B", "text": "", "asset_ids": ["fma-2016-q005-choice-B-01"]}
      ],
      "answer": {"text": null, "label": null, "evidence": "not-provided"},
      "classification": {
        "schema": "physics-question-classification/v1",
        "status": "review",
        "curriculum": {
          "course_id": "fma",
          "unit_id": "kinematics",
          "topic_id": "graphs",
          "subtopic_ids": ["motion-graphs"]
        },
        "physics_domain": "mechanics",
        "primary_topic": {
          "name": "Motion graph interpretation",
          "evidence": "The correct option is selected by interpreting the physical meaning of the plotted variables."
        },
        "secondary_topics": [],
        "knowledge_points": [
          {
            "name": "Graph slope/shape encodes a physical relationship",
            "role": "required",
            "evidence": "The student must connect the graph representation to the motion model."
          }
        ],
        "solution_models": [
          {
            "name": "Graph representation relationship",
            "kind": "representation",
            "role": "primary",
            "evidence": "The graph itself is the governing representation used to decide the answer."
          }
        ],
        "skills": [
          {
            "id": "graph_interpretation",
            "evidence": "The student must read a graph rather than substitute directly into a formula."
          }
        ],
        "difficulty": {
          "rubric_id": "pocket-cosmos-timbad",
          "rubric_version": "1.0",
          "level": null,
          "overall_level": null,
          "review_status": "NEEDS_REVIEW",
          "rejection_reason": null,
          "question_quality_flags": [],
          "drivers": [
            "Visual options have not yet been inspected."
          ],
          "overall_reason": "",
          "boundary_reason": "",
          "timbad": {
            "T": {
              "score": null,
              "rationale": "",
              "evidence": ""
            },
            "I": {
              "score": null,
              "rationale": "",
              "evidence": ""
            },
            "M": {
              "score": null,
              "rationale": "",
              "evidence": ""
            },
            "B": {
              "score": null,
              "rationale": "",
              "evidence": ""
            },
            "A": {
              "score": null,
              "rationale": "",
              "evidence": ""
            },
            "D": {
              "score": null,
              "rationale": "",
              "evidence": ""
            }
          },
          "primary_bottleneck": "NONE",
          "secondary_bottleneck": "NONE",
          "key_insights": [],
          "insight_depth": "NONE",
          "solution_outline": [],
          "final_answer": null,
          "topic": "Motion graphs",
          "subtopic": "Graph interpretation",
          "prerequisites": [],
          "key_skills": [],
          "math_tools": [],
          "rating_confidence": "LOW",
          "needs_human_review": true,
          "review_notes": "Inspect all option graphs before independently solving and rating.",
          "assessed_at": null,
          "reviewer": null
        },
        "confidence": 0.5,
        "review": {"reviewed": false, "method": "pending-visual-option-review"},
        "derived_fields_version": "1.0"
      },
      "course": "F=ma",
      "unit": "Kinematics",
      "topic": "Graphs",
      "subtopics": ["Motion graphs"],
      "knowledge_points": ["Graph slope/shape encodes a physical relationship"],
      "solution_models": ["Graph representation relationship"],
      "skills": ["graph_interpretation"],
      "difficulty": null,
      "asset_ids": [
        "fma-2016-q005-choice-A-01",
        "fma-2016-q005-choice-B-01"
      ],
      "layout_blocks": [],
      "layout_review": null,
      "extraction": {"method": "pdf-text-layer", "text_reviewed": true, "confidence": 0.98},
      "requires_manual_review": true,
      "review_reasons": ["semantic_classification_uncertain"]
    }
  ]
}
```

## Exam year contract

Every published question has one canonical four-digit `year` integer and the same value in `source.year`. `tags` also contains `year:YYYY`. `year_evidence` records how the year was established. Never infer year from question content.

## Asset records

Stem/shared figure:

```json
{
  "id": "fma-2016-q005-stem-01",
  "file": "assets/figures/fma-2016-q005-stem-01.png",
  "source": {
    "file": "assets/source/2016_Fma_exam.pdf",
    "page": 3,
    "bbox": [96.2, 188.4, 402.6, 331.8]
  },
  "role": "stem",
  "owners": ["fma-2016-q005"],
  "reviewed": true,
  "crop": {
    "render_zoom": 6,
    "method": "source-pdf-bbox",
    "reviewed": true,
    "review_sha256": "<sha256 of final image bytes>",
    "review_source_sha256": "<sha256 of source PDF bytes>",
    "reviewed_source_bbox": [96.2, 188.4, 402.6, 331.8],
    "source_neighborhood_reviewed": true,
    "review_method": "source-page-halo+final-file",
    "ignore_nearby_text": []
  }
}
```

Choice figure:

```json
{
  "id": "fma-2016-q005-choice-A-01",
  "file": "assets/choices/fma-2016-q005/A-01.png",
  "source": {
    "file": "assets/source/2016_Fma_exam.pdf",
    "page": 3,
    "bbox": [101.0, 355.2, 205.4, 436.8]
  },
  "role": "choice",
  "choice_label": "A",
  "choice_index": 1,
  "owners": ["fma-2016-q005"],
  "reviewed": true,
  "crop": {
    "render_zoom": 6,
    "method": "box+autotrim",
    "reviewed": true,
    "isolated_choice": true,
    "review_sha256": "<sha256 of final image bytes>"
  }
}
```

## Choice asset contract

- A final `choice` asset belongs to exactly one question.
- It has one uppercase `choice_label` matching a real entry in `question.choices`.
- `choice_index` is a positive integer. It is `1` for the normal one-image-per-option case.
- Final files live under `assets/choices/<question-id>/` and use `<LABEL>-<NN>.<ext>`.
- The matching choice object contains the asset ID in `choices[].asset_ids`.
- The same asset ID also remains in the question's top-level `asset_ids` for downstream compatibility.
- `crop.isolated_choice: true` means the final crop was visually checked to contain only that semantic option and no neighboring option image/label/prose.
- A combined multi-option strip/grid is never a valid final choice asset.
- If an option has multiple independent images, use unique indices (`A-01`, `A-02`, ...).
- A figure shared by all options is a `stem` or `shared` asset, not duplicated as four choice assets.

Valid asset roles are `stem`, `choice`, `shared`, and `answer`. `reviewed: true` means the final file itself was visually inspected after the last modification.

Always retain an `answer` object. For key-only sources, populate only `answer.label` and set `answer.text` to null; source provenance belongs in metadata, not student-facing solution text. For source-provided worked solutions, extract text and reviewed answer figures without inventing reasoning. Mathematical source remains Markdown+LaTeX.


## Visual provenance position

For every final visual asset, record its source page. For `stem` and `shared` assets, v2.3 strict validation also requires:

```json
"source": {
  "file": "assets/source/source.pdf",
  "page": 12,
  "bbox": [x0, y0, x1, y1]
}
```

`bbox` is the semantic source region in PDF points, not a later post-autotrim pixel box.

## Narrative placement

`question.asset_ids` means ownership, not presentation order.

For every question with a `stem` or `shared` visual, add explicit `question.layout_blocks` and `question.layout_review`. The exact contract is in `references/narrative-layout.md`.

Choice visuals remain bound through `choices[].asset_ids`; they are not inserted into narrative `layout_blocks`.


## Visual review seal · v2.4

`reviewed: true` is no longer sufficient by itself in strict mode.

For every final visual asset, `crop.review_sha256` must equal the SHA-256 of the current image file. For `stem` / `shared` assets, strict mode additionally requires:

- `crop.review_source_sha256` matching the current source PDF;
- `crop.reviewed_source_bbox` matching `source.bbox`;
- `crop.source_neighborhood_reviewed: true`.

Run `scripts/seal_asset_review.py` only after inspecting the final image and the source-halo preview. Any destructive recrop invalidates these fields automatically.

Strict validation also examines the source page itself. A text, drawing, or embedded image that crosses `source.bbox` is a hard failure. Short nearby text objects (common for circuit values, Greek symbols, axis labels, and units) are treated as likely omitted labels. If a nearby text object is genuinely unrelated (e.g. a neighboring caption), list its exact text in `crop.ignore_nearby_text` only after visual confirmation.


## Semantic classification · v2.5

`question.classification` is the canonical semantic record. The flat fields `course`, `unit`, `topic`, `subtopics`, `knowledge_points`, `solution_models`, `skills`, `difficulty`, and semantic tag prefixes are derived search/compatibility mirrors.

Every bank must also contain `classification-taxonomy.json` using `physics-bank-curriculum-taxonomy/v1`. Question curriculum IDs must resolve to that file with valid parent-child relationships.

See:

- `references/semantic-classification.md`
- `references/semantic-taxonomy.json`
- `references/classification-taxonomy-template.json`

Run `scripts/derive_semantic_tags.py` after model classification and before semantic validation. Do not manually maintain the derived semantic prefixes.


## Math normalization · v2.6

Student-facing canonical text remains `markdown+latex`. Any explicit LaTeX command, underscore subscript, or caret superscript must be inside `$...$` or `$$...$$`.

Valid:

```json
"stem": "The kinetic energy is $U_K$ and the initial speed is $v_0$."
```

Invalid:

```json
"stem": "The kinetic energy is U_K and the initial speed is v_0."
```

See `references/math-normalization.md`. Strict bank validation rejects the invalid form.

## Answer extraction · v2.7

The canonical `answer` object supports optional `kind` values `key_only`, `worked_solution`, and `not_provided` (older answer objects without `kind` remain valid).

**Key-only:** `{"kind":"key_only","label":"C","text":null,"evidence":"official-key","source":{"file":"assets/source/key.pdf","page":2}}`. Do not put exam-board attribution or any explanation invented by the model in `answer.text`.

**Worked solution from source:** `answer.text` contains the real source's explanation/derivation; `answer.asset_ids` references reviewed `role=answer` figures under `assets/answers/<question-id>/`. All answer figures must also appear in the question's top-level `asset_ids` for existing tool compatibility. `answer.layout_blocks` is the answer-only reading order and must reproduce the complete `answer.text` and each answer diagram once. `answer.extraction.reviewed: true` and `answer.layout_review.reviewed: true` are mandatory under strict validation for image-bearing worked answers.

Answer assets require source document file, 1-based source page and PDF-coordinate bbox. Their `crop.review_sha256`, `crop.review_source_sha256`, `crop.reviewed_source_bbox` and `crop.source_neighborhood_reviewed` are sealed like stem/shared figures. Note: an answer's source page may differ from `question.source_pages`; the latter refer to the question, not the key.

The untouched original answer page remains in `assets/source` as the audit source. Any omitted signature/watermark/header must be recorded under `answer.excluded_non_instructional` with `kind`, `source_bbox` and an explicit `reason`. If a mark overlaps explanatory information, retain it or flag manual review, never erase physics content.

See `references/answer-extraction.md` for the extraction protocol.


## Worked-answer source vision gate · v2.9

New `answer.kind="worked_solution"` records must carry the whole-answer `answer.source.bbox` and a source-SHA-bound `answer.visual_review`. The review confirms instructional text/math/diagrams and omission safety and is independent of the separate SHA seals on cropped answer figures. See `references/answer-extraction.md` for the review-sheet rendering and sealing commands. Key-only records retain a bare label with no generated instructional prose.
