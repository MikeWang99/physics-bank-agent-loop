---
name: physics-bank
description: Use when building or reviewing physics question banks from exam PDFs, including source-faithful text and answer extraction, visual assets, curriculum classification, or Pocket Cosmos TIMBAD L1–L7 difficulty assessment.
---

# Physics Bank v3.0.0-rc.5 (candidate)

Build a reusable, auditable question bank. The governing rule is **source fidelity first**: the model may enrich metadata, but it must not silently repair, shorten, paraphrase, merge, or guess source text, source metadata, or visual option content.

## Required output

Create a `question-bank/` bundle containing:

- `questions.json` using schema version `2.0`.
- `assets.json` using schema version `2.0`.
- `assets/source/` with source papers supplied by the user.
- `assets/figures/` with final reviewed stem/shared figures only.
- `assets/choices/<question-id>/` with final reviewed **individual choice images** only.
- `assets/answers/<question-id>/` with independent, source-reviewed **worked-answer diagrams** (when the answer source contains instructional graphics).
- `extraction/raw_pages.json` and `extraction/question_drafts.json` as the audit trail.
- `knowledge-taxonomy.json`, a validated export of the currently pinned unified website taxonomy for v2. Its version, source commit, Git blob, and expected node count are defined by `references/knowledge-taxonomy.lock.json`; do not hardcode an older count. Legacy v1 banks retain `classification-taxonomy.json`.
- Per-question `classification` objects using `physics-question-classification/v2` (v1 remains supported).

For v2, year is optional. Preserve historical years, provenance and IDs; do not generate required `year:YYYY` tags.

Read `references/answer-extraction.md`, `references/text-extraction.md`, `references/math-normalization.md`, `references/asset-manifest.md`, `references/choice-assets.md`, `references/narrative-layout.md`, `references/knowledge-classification-v2.md`, `references/difficulty-assessment.md`, and `references/timbad-difficulty-rubric.md` (legacy v1 also requires the semantic references) before execution.

## Stage A — faithful extraction (mandatory; do not skip)

1. Inventory source PDFs and answer keys.
2. Run:

   ```bash
   python "$SKILL_DIR/scripts/extract_question_text.py" source.pdf \
     --outdir question-bank/extraction \
     --id-prefix <stable-prefix>
   ```

3. Optionally record a **verified** exam year. Never infer a date merely to satisfy a schema. The existing script remains available for verified year and legacy v1 sources:

   ```bash
   python "$SKILL_DIR/scripts/stamp_exam_year.py" \
     question-bank/extraction/question_drafts.json

   python "$SKILL_DIR/scripts/stamp_exam_year.py" \
     question-bank/extraction/question_drafts.json --year 2016
   ```

4. Inspect `question_drafts.json` and the rendered/source pages. Resolve every `requires_manual_review` item. If a PDF is scan-only or the text layer is corrupted, visually transcribe from the page image; record the method and keep the raw draft for comparison.
5. Preserve `raw_source_text`, `source_pages`, original numbering, choices, shared context, and any known year metadata. Shared textual setup must be copied into each final question's `context` so every question is self-contained.
6. Preserve source geometry. `raw_pages.json` line bboxes are evidence for reading order; every final stem/shared asset must later record its source `page` and semantic PDF-point `bbox`.
7. Only after visual/text comparison set `extraction.text_reviewed: true`.

Never infer omitted clauses from physics knowledge. Uncertain symbols/sentences require manual review; an absent year alone does not block v2 publication.

### Learner-facing text and source conditions — required

- Preserve original printed textbook figure IDs, PDF/printed page numbers, OCR artifacts, and production notes in `raw_source_text`, `source`, `extraction`, or the asset manifest. Do not put them in learner-visible `context`, `stem`, choices, or text layout blocks. The current Publisher displays `context + stem`; context is not private metadata.
- If a source question points to a figure, match it by source page, printed figure ID, and original question identity. Attach that question's own reviewed `stem/shared` figure and place it exactly once in `layout_blocks`. In the learner copy, refer to “the diagram shown” when needed; do not leave a book-specific `Fig. 4–xx` reference.
- Do not place labels such as `Source figure description` or `Source-derived diagram description` in learner text as a substitute for an image. If a figure cannot be isolated or faithfully reconstructed, mark the question `requires_manual_review` and keep it out of the publishable bank until the figure is resolved.
- A chapter or section instruction can be a real physical condition, but proximity alone does not prove its scope. Verify the heading, page, and affected question range. Record its exact wording in `extraction.shared_source_instructions[]` with `source_heading`, positive `source_page`, and `reviewed: true`. When it changes the model and applies to a question, preserve that condition in learner-ready prose without mechanically repeating the heading's bracketed label, such as `[Ignore friction.]`. Do not silently drop a required condition or infer one from the solution.
- A condition stated in an individual question remains valid source content. Do not globally remove words such as `friction`, `frictionless`, `ignore`, or `neglect`; compare each condition with the question text and verified shared instructions.
- Before setting `extraction.text_reviewed: true` and before independent acceptance, inspect the exact learner prompt the runtime will display (`context + stem`, choices, and figure order). The strict validator blocks source figure/page leaks, description labels, missing owned figures, unsupported physical assumptions, and verbatim copies of verified shared physical instructions; the independent Reviewer must still catch semantic changes the validator cannot recognize.

## Stage B — source-faithful normalization

Create stable final IDs, preserve available year/source metadata, attach answer evidence, and normalize mathematical notation to canonical `markdown+latex`. Missing official answers remain `not-provided`; do not solve merely to fill the answer field.

### B0. Source-faithful answer extraction — mandatory in v2.9

**Always distinguish the answer source from the solution content students should see.**

- If an official/user-provided key gives only a single option, store `answer.kind: "key_only"`, `answer.label: "A"`, and `answer.text: null`. The `evidence` code and full `answer.source`/provenance live in metadata only. Never generate `Official answer: A.`, `According to AAPT...`, or an invented worked explanation.
- If the source contains a real explanation/derivation/answer figures, use `answer.kind: "worked_solution"`. Transcribe **only** the actual instructional prose/formulae from the source to `answer.text`. Render independent answer diagrams to `assets/answers/<question-id>/` with `role: "answer"`, record each in both question and answer asset IDs, preserve the answer text/figure order using `answer.layout_blocks`, and visually review and seal the exact final figures against the original answer page.
- Keep the original untouched answer PDF/image under `assets/source/`. Record `answer.source`, `answer.extraction` and, for omitted signatures/watermarks/headers, `answer.excluded_non_instructional` with source bboxes and reasons. Never remove an overlapping signature if doing so would erase derivation, a formula, or diagram labels.
- If the answer itself is missing or ambiguous, use `not-provided` and manual review rather than guessing.

Full schema, source-fidelity boundaries, and examples: `references/answer-extraction.md`.

For every new worked source, visually inspect the unchanged source and a rendered answer review sheet, then seal `answer.visual_review` with the exact original source SHA-256, page and whole-answer bbox. Never declare visual review based only on OCR or a generated thumbnail. Keep uncertain symbols/signatures in manual review. The complete procedure and commands are in `references/answer-extraction.md`.

Run the focused answer QA after building canonical answers:

```bash
python "$SKILL_DIR/scripts/validate_answer_content.py" \
  question-bank/questions.json --assets question-bank/assets.json \
  --report question-bank/answer-validation-report.json
```

The normal strict `validate_bank.py` also enforces this contract.

### B1. Math normalization — mandatory

PDF text layers often flatten visual mathematical typography. Compare the final student-facing text against the rendered source page and encode the **same source notation** explicitly.

Examples:

```text
U_K       → $U_K$
v_0       → $v_0$
mu_s      → $\mu_s$
\mu_s     → $\mu_s$
F_net     → $F_{\text{net}}$
x^2       → $x^2$
```

Rules:

- any LaTeX command, underscore subscript, or caret superscript in canonical student-facing text must be inside `$...$` or `$$...$$`;
- do not infer a different symbol from physics knowledge when the source is ambiguous;
- do not globally reinterpret underscores downstream; the bank must carry the math semantics;
- preserve Stage A `raw_source_text` unchanged for audit;
- if the source symbol cannot be established confidently, keep the question in manual review.

Run the focused diagnostic after normalization:

```bash
python "$SKILL_DIR/scripts/validate_answer_content.py" \
  question-bank/questions.json --assets question-bank/assets.json \
  --report question-bank/answer-validation-report.json

python "$SKILL_DIR/scripts/validate_math_markup.py" \
  question-bank/questions.json \
  --report question-bank/math-validation-report.json
```

The normal strict `validate_bank.py` gate also enforces the same rule.

Stage B may normalize whitespace and mathematical notation but must preserve prose meaning and every physical condition. Compare final context/stem/choices against Stage A before publication.

Do **not** assign knowledge UID/difficulty tags yet. Classification happens only after the complete text and all relevant figures/visual choices have been reconstructed and reviewed.

## Figure pipeline

### Stem/shared figures

1. Discover candidates independently of captions:

   ```bash
   python "$SKILL_DIR/scripts/discover_pdf_assets.py" source.pdf \
     --outdir "$TMPDIR/question-bank-discovery" --zoom 6
   ```

   Discovery is **non-authoritative**. Candidate rasters are only navigation/review aids. The detector expands graphic clusters to absorb nearby short text labels such as voltage values, symbols, axis labels, and units, but a candidate must never become the irreversible parent image for a published asset.

2. Determine ownership only after question boundaries exist. Classify stem-level assets as `stem` or `shared` and publish them under `assets/figures/`.
3. Choose the semantic region on the **original source page**, not on a discovery candidate. Record it in `assets.json -> source.page + source.bbox`.
4. Render the final asset directly from the original PDF:

   ```bash
   python "$SKILL_DIR/scripts/render_source_asset.py" source.pdf \
     --page <1-based-page> --bbox X0 Y0 X1 Y1 \
     --output question-bank/assets/figures/<asset>.png \
     --report "$TMPDIR/<asset>-source-review.json"
   ```

   This also produces a `_debug/*source-halo.png` preview with the kept bbox marked in source context. If it reports nearby short-text risks, enlarge the bbox. Only explicitly irrelevant text may be documented in `crop.ignore_nearby_text`.

5. Use `blocks → mark → preview → visual inspection → box/autotrim` only for cleanup **after** a source-faithful render. Any destructive recrop automatically invalidates an existing review seal.
6. Open both the **final file after the last modification** and the source-halo preview. Verify labels, axes, arrowheads, endpoints, dimensions, scale information, and that no neighboring prose/answer/footer leaked in.
7. Seal that exact reviewed state:

   ```bash
   python "$SKILL_DIR/scripts/seal_asset_review.py" \
     question-bank/assets.json --asset-id <asset-id> \
     --confirm-source-neighborhood
   ```

   The seal stores the final-image SHA-256, source-PDF SHA-256, and reviewed source bbox. Any later file/bbox/source change makes strict validation fail until the asset is reviewed and sealed again.
8. Reconstruct the original text/figure reading order in `question.layout_blocks`. Every figure block must carry a `source_anchor`; every stem/shared asset must appear exactly once.
9. Compare the reconstructed order against the rendered source page. Only then set `layout_review.reviewed: true` on the question.

### Worked-answer diagram pipeline · v2.9

When an official solution or user-provided answer image contains instructional diagrams, use the same source-page rendering and SHA-sealed review rules as stem/shared figures, but with **`role: "answer"`** and files under `assets/answers/<question-id>/`.

Do not put signatures, publisher attributions or answer-key boilerplate into canonical `answer.text`; retain original source for audit and document excluded non-instructional regions. An exclusion bbox must be inside the reviewed answer region and cannot overlap a retained instructional diagram; never erase ambiguous overlapping information. Use `answer.layout_blocks` (separate from question stem `layout_blocks`) to retain the original worked solution reading order. Text in a diagram must be preserved, not guessed.

### Visual choice pipeline — mandatory when any option contains an image

Visual choices are first-class assets. **Never publish a combined A/B/C/D option strip or grid as one final asset.** Each semantic option image must be independently cropped and independently reviewed.

For each visual option:

1. Identify its owner question and choice label before cropping.
2. Crop that option independently. Exclude neighboring choice images and, when practical, exclude the printed A/B/C/D label itself because the label is represented structurally in JSON.
3. Run `blocks → mark → preview → visual inspection → crop` for that option alone.
4. Verify the final crop contains the complete intended option image and no content from any other option. Only then set:

   ```json
   {
     "role": "choice",
     "choice_label": "A",
     "choice_index": 1,
     "reviewed": true,
     "crop": {"reviewed": true, "isolated_choice": true}
   }
   ```

5. Add the asset ID to both:
   - the question's top-level `asset_ids` for downstream compatibility; and
   - the matching `choices[].asset_ids` entry for precise option binding.
6. Canonicalize the files and JSON links:

   ```bash
   python "$SKILL_DIR/scripts/organize_choice_assets.py" \
     question-bank/questions.json \
     --assets question-bank/assets.json \
     --apply \
     --report question-bank/choice-asset-report.json
   ```

Final choice files must live at:

```text
assets/choices/<question-id>/<LABEL>-<NN>.<ext>
```

Examples:

```text
assets/choices/fma-2016-q005/A-01.png
assets/choices/fma-2016-q005/B-01.png
assets/choices/fma-2016-q005/C-01.png
assets/choices/fma-2016-q005/D-01.png
```

If one option genuinely contains multiple independent images, give them unique positive `choice_index` values (`A-01`, `A-02`, ...). Do not use `choice_index` to represent neighboring answer options.

A diagram shared by all choices is **not** a choice asset; store it as `stem`/`shared`. A text+image option keeps its text in `choices[].text` and its image IDs in `choices[].asset_ids`.

A detection script finding no candidates is not evidence that no diagram exists. Scan relevant question/choice regions visually, especially for full-page raster/scanned PDFs.

## Narrative layout gate — mandatory in v2.3

The bank must preserve **where** each stem/shared visual occurs, not merely that it belongs to the question.

For any question with one or more `stem` / `shared` assets:

1. Record each asset's physical source location in `assets.json`:
   - `source.file`
   - `source.page`
   - `source.bbox: [x0, y0, x1, y1]`
2. Build ordered `question.layout_blocks` using only source-faithful `text` and `figure` blocks.
3. Ensure the concatenated text blocks preserve all of `context + stem`; do not omit prose merely because a figure interrupts it.
4. Give every figure block a `source_anchor`:
   - `question_start` / `question_end`, or
   - `before` / `after` with a short exact source phrase.
5. Set `question.layout_review = {"reviewed": true, "method": "..."}` only after visual comparison with the source page.

`choices[].asset_ids` remains the placement mechanism for visual answer choices; choice images do not belong in narrative `layout_blocks`.

Do not rely on downstream PDF generation to infer layout. `homework-pdf` already consumes `layout_blocks` as authoritative order, so the question bank must supply them correctly.



## Stage C — Unified Knowledge UID classification · v3.0

**One authoritative knowledge tree; one primary UID per reviewed question.** Read
references/knowledge-classification-v2.md, references/difficulty-assessment.md and
the complete, unaltered references/timbad-difficulty-rubric.md before proceeding.

### C0. Pin and synchronize the authoritative taxonomy

The ONLY taxonomy authoring source is MikeWang99/pocket-cosmos-online at
src/data/pocket_cosmos_physics_taxonomy_v1.json. This repository pins the website
commit, Git blob hash and taxonomy version in references/knowledge-taxonomy.lock.json.
Do not create UIDs or maintain another manually edited tree. From a checkout of
the pinned website commit, run:

    python "$SKILL_DIR/scripts/sync_knowledge_taxonomy.py" \
      --input ../pocket-cosmos-online/src/data/pocket_cosmos_physics_taxonomy_v1.json \
      --output question-bank/knowledge-taxonomy.json

The sync checks node identity, hierarchy, names, parent, counts, canonical UIDs,
Git blob identity and version. Archive its verified export with the question bank.
Taxonomy changes require a separate, explicitly reviewed lock update.

### C1. Establish reliable origin before reading a PDF

Require an explicit, sourced document-level source_system (ap-physics-1,
ap-physics-2, ap-c-mech, ap-c-em, igcse, a-level, bpho, physics-bowl, competition).
For generic competition preserve the exact contest in source_event (e.g. fma).
A single-source PDF gives all questions that source_system; mixed collections
require per-question verified origin. Unknown origin => needs_review, never guess.
Source origin is independent of difficulty, UID and course suitability.

For new v2 questions source year is OPTIONAL. Do not invent an unverified year
or generate a mandatory year:YYYY tag. Preserve all already known source years,
source_refs, question IDs and immutable version history.

### C2. Full solution and candidate analysis, never keyword-only

Classify only AFTER text, context, all choices, mathematics, figures and choice
images are compared to the source. Independently solve to identify the full
required concept set and latest required prerequisite. Save concise audit facts
in classification.physics_analysis (required_concepts, solution_summary,
latest_required_reason) without hidden chain-of-thought.

Search real UIDs by running:

    python "$SKILL_DIR/scripts/search_knowledge_nodes.py" \
      --taxonomy question-bank/knowledge-taxonomy.json \
      --query "circular motion energy"

That script retrieves candidates; it does NOT perform validated physics
classification. Compare a few real candidate nodes by target, complete solution
coverage, later integrated prerequisites, specificity and counterevidence.
Circular Motion + Energy generally belongs to the appropriate later integrated
node, NOT basic Circular Motion. Examine collisions/momentum and other chapters
where applicable.

### C3. Independent classification review and rejection

Record exactly one real primary_knowledge_uid, status, confidence, candidate
decisions/reasons and taxonomy version + SHA256. Independent review must revisit
the physics, look for cross-chapter errors, and record review.reviewed, method,
initial_uid, independent_uid, agreement and cross_chapter_checked.

Disagreement, missing crucial source content, absent appropriate node, or
insufficient evidence => status needs_review, with reason, candidates and
proposed missing topic in an independent classification-review.json audit file.
Do not force a valid but wrong UID. Do not auto-expand the authority. Confidence
is NOT measured accuracy. Use educator-reviewed gold tests before accuracy claims.

### C4. Preserve complete TIMBAD v1.0 difficulty contract, unchanged

Read both the full rubric and difficulty-assessment integration spec. Preserve
six axes T/I/M/B/A/D (independent 0–2 ratings), all original audit fields,
verified solution, boundary reasons, bottlenecks, insights, prerequisites, skills,
review state, independent L1–L7 judgement. The axis total DOES NOT determine L.
L0 is REJECTED, NEEDS_REVIEW may be unrated. Never map old 1–5 to L1–L7 and
never change only numeric level on a previously approved audit. Independent
solution notes are only for difficulty review, not student-facing official answers.

### C5. Minimal v2 mirrors and dual-schema compatibility

New schema physics-question-classification/v2 uses stable Question ID,
source_system, one verified primary UID and the FULL TIMBAD difficulty record.
Do not generate bank-specific unit/topic/subtopic trees, specialty_groups,
specialty_ids or repetitive domain/topic/model/skill tags for v2. A v2
approved difficulty emits numeric 1–7; rejected, unresolved and unrated emit null.
Keep teacher-owned custom tags and all historical evidence.

    python "$SKILL_DIR/scripts/derive_semantic_tags.py" question-bank/questions.json
    python "$SKILL_DIR/scripts/validate_semantic_classification.py" question-bank/questions.json \
      --knowledge-taxonomy question-bank/knowledge-taxonomy.json --strict

Legacy v1 banks still use their original classification-taxonomy.json, derivation
and validation contract. When a bundle mixes v1/v2, pass BOTH --taxonomy
and --knowledge-taxonomy arguments. Never silently convert v1 topic IDs into a
knowledge UID. Full PDF/text/math/asset/answer/TIMBAD strict gates remain
mandatory for both schemas.

## Final hard gate

Run all validators:

```bash
python "$SKILL_DIR/scripts/validate_bank.py" question-bank/questions.json \
  --assets question-bank/assets.json \
  --strict --require-text-review \
  --report question-bank/validation-report.json

python "$SKILL_DIR/scripts/validate_math_markup.py" \
  question-bank/questions.json \
  --report question-bank/math-validation-report.json

python "$SKILL_DIR/scripts/validate_year_metadata.py" \
  question-bank/questions.json \
  --report question-bank/year-validation-report.json

python "$SKILL_DIR/scripts/validate_semantic_classification.py" \
  question-bank/questions.json \
  --knowledge-taxonomy question-bank/knowledge-taxonomy.json \
  --strict \
  --report question-bank/semantic-validation-report.json
```

Do not present a bank as complete if validation fails. In v2.8 the semantic validator also enforces the TIMBAD record contract and publication review gates; numerical validation cannot establish that a physics rating is correct. In v2.9 strict validation requires a source-SHA-bound worked-answer visual review, whole-answer bbox and safe noninstructional exclusions. In v2.7 strict validation additionally checks answer-key minimality, source-provenance isolation and source-sealed illustrated solutions; v2.6 strict validation rejects bare/unbalanced mathematical markup such as `U_K`, `v_0`, `x^2`, or `\mu_s` outside math delimiters. The v2.5 semantic gate and all v2.4 visual-integrity protections remain mandatory.

## Stability rules

- Never skip Stage A and jump directly from PDF to polished JSON.
- Never invent a year; missing year alone does not block v2.
- Never publish v2 without one reviewed UID resolving against the pinned website taxonomy; v1 still resolves against its bank taxonomy.
- Never replace a label-only official answer with an invented explanation or source-attribution prose.
- Never publish an answer diagram without the unchanged source, explicit answer-only placement and SHA-sealed visual review.
- Never assert the full worked answer was visually checked unless the source plus contact sheet were actually inspected and the answer review seal matches source SHA and bbox.
- Never allow signatures/watermarks to replace, obscure, or erase educational equations or labels.
- Never publish LaTeX syntax, underscore subscripts, or caret superscripts as ordinary prose; encode them in `$...$` / `$$...$$`.
- Never use only page screenshots as question content when readable text can be represented structurally.
- Never discard cross-page continuation text.
- Never hide uncertainty by lowering confidence without a review flag.
- Never mark a crop reviewed before inspecting the final post-crop file **and its source-halo preview**, then sealing that exact state.
- Never create a published stem/shared asset by repeatedly cropping a discovery candidate; final pixels must come directly from the original PDF source bbox.
- Never rely on `reviewed: true` alone. A valid review requires matching image/source SHA-256 seals and the exact reviewed source bbox.
- **Never keep multiple answer options in one final choice-image file.**
- **Never place final choice images in `assets/figures/`; use `assets/choices/<question-id>/`.**
- **Never bind one choice asset to multiple questions.**
- Never publish unresolved asset IDs, orphan assets, duplicate IDs, or unreviewed text.
- Never publish a stem/shared visual without explicit source geometry and narrative placement.
- Never let a downstream renderer guess whether a figure belongs before or after a sentence.
- Never classify a question from keywords alone; read the full text and relevant figures first.
- Never treat a visible object/topic word as the primary topic unless it actually organizes the solution.
- Never hand-edit generated tags; v2 retains only the primary UID and approved difficulty mirror while preserving custom labels.
- Re-running on the same PDF should preserve stable IDs, source boundaries, existing year metadata, choice-asset slots, source bboxes, and reviewed layout order unless human review intentionally corrects them.

