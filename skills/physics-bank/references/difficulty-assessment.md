# Pocket Cosmos TIMBAD integration · physics-bank v2.8

## Authority and when to read

Read the **complete** [TIMBAD rubric v1.0](timbad-difficulty-rubric.md) before rating a question. It is the user's supplied operational rubric, preserved verbatim, not an exam-board standard or a statistically validated scale. This file adapts its JSON to physics-bank; it does not replace the scoring tables, boundaries, SOP, examples, or calibration rules.

The rubric references a separate TIMBAD/FMA PDF. That PDF is not bundled here. Its described examples are provisional anchors from the supplied rubric, not newly verified source questions. Do not claim access to that PDF or invent missing L6/L7 anchors.

## Scoring workflow

1. After Stage A/B and visual review, inspect the full question, choices and required figures. Quality-gate first. Missing critical material is `NEEDS_REVIEW`, never a guessed L0 or L7.
2. Independently establish a reliable route and check the result/option and physical constraints. Assume prerequisite physics and routine math are mastered, but the student has not seen this specific question or memorized its trick. Use a reasonably discoverable, reliable solution; neither an expert-only shortcut nor an intentionally cumbersome solution should distort the rating.
3. Record a **concise** solution audit, not private chain-of-thought. Assess each TIMBAD dimension against rubric §4 with a score, rationale and specific evidence, including why a zero is direct.
4. Identify real insights and bottlenecks. Determine L independently from rubric §§5–6. Do not sum dimensions or count the same obstacle several times. Math tools, exam source, prerequisite gaps and student errors do not themselves determine difficulty.
5. Explain neighboring-level boundaries, especially L4/L5 (complex standard combination vs non-obvious breakthrough), L5/L6 (does one local hint unlock a standard finish?), and L6/L7 (specific creative demand). Follow §§9–10 for multipart questions, alternative solutions, boundaries and provisional anchors.
6. Complete confidence and review state. LOW confidence or unresolved material/reviewer ambiguity requires human review. An anchor/reviewer discrepancy of two levels without an adequate resolution triggers human review. Use rubric §13 for calibration; do not manufacture completion times, student statistics or review identities.

## Canonical storage

Store the adapted §11 rating object under **`question.classification.difficulty`**. The enclosing `question.id` is the rubric's `question_id`; source/exam/year/number remain in canonical question provenance, rather than duplicated guessed fields. `classification` continues to use `physics-question-classification/v1`; bundle schema stays `2.0`. The difficulty contract is identified separately by `rubric_id` and `rubric_version`.

Required for an APPROVED rating:

| Field | Type / contract |
|---|---|
| `rubric_id`, `rubric_version` | `"pocket-cosmos-timbad"`, `"1.0"` |
| `review_status` | `APPROVED`, `REVISE`, `NEEDS_REVIEW`, `REJECTED` |
| `overall_level` | `L1`–`L7`; `L0` only for REJECTED; null for NEEDS_REVIEW |
| `level` | Numeric mirror of overall_level, 0–7/null; **not a second rating** |
| `drivers` | Nonempty concise evidence array, retained for classification compatibility |
| `timbad` | Exactly `T,I,M,B,A,D`; each `{score: integer 0/1/2, rationale: string, evidence: string}` |
| `overall_reason`, `boundary_reason` | Concrete overall and adjacent-level audit evidence |
| `primary_bottleneck`, `secondary_bottleneck` | `T/I/M/B/A/D/NONE`; distinct when non-NONE |
| `key_insights`, `insight_depth` | String array; `NONE/MODEST/SUBSTANTIAL/DEEP/EXCEPTIONAL`; no invented insights |
| `solution_outline`, `final_answer` | Brief reliable audit statements and independently checked result |
| `topic`, `subtopic` | Curriculum-aligned rating snapshot; canonical curriculum IDs remain under classification.curriculum |
| `prerequisites`, `key_skills`, `math_tools` | String arrays; tools describe knowledge used, not mathematical difficulty A |
| `rating_confidence`, `needs_human_review` | `HIGH/MEDIUM/LOW`, boolean |
| `question_quality_flags`, `rejection_reason` | String array; null unless rejected, then a rubric §3.1 reason code |

Recommended: `review_notes`, `assessed_at` (ISO 8601/null), `reviewer` (known identifier/null), `estimated_minutes` (supported value/null), `curricula`, `question_type`. Preserve additional rubric fields such as part assessments or calibration/reviewer comparisons when used; resolve any triggered human review before approval. If uncertain about topic/subtopic use `Unknown` and the classification review gate, not a fabricated taxonomy mapping.

`key_skills` in this audit uses rubric §8.3's teaching vocabulary. It does **not** replace the controlled `classification.skills[].id` list. Those must still use semantic-taxonomy.json. The rubric's math vocabulary is recommended, not an automatic level classifier.

### Source answer boundary

`difficulty.final_answer` and `difficulty.solution_outline` are **assessment metadata** from the independent check. They never become `question.answer.text`, `answer.label`, `answer.layout_blocks`, or official answer evidence. `derive_semantic_tags.py` must not copy them there. Downstream consumers must keep the rating audit separate from the student-facing official solution.

When no official answer is supplied, Stage B still leaves `question.answer.evidence: "not-provided"`. The model may solve for rating, storing only the audit result here. A supplied key disagreement requires `REVISE`/`NEEDS_REVIEW` and review notes; preserve the source key. If no reliable solution can be established, use NEEDS_REVIEW/null, not an assumed high difficulty.

## State and publication gates

| Review state | Canonical difficulty | Storage / publication |
|---|---|---|
| APPROVED | L1–L7, numeric 1–7, all six scores and evidence | Strict publication only with no unresolved human review and no LOW rating confidence |
| REVISE | Tentative L1–L7 when a reliable route supports it, otherwise null | Non-strict audit only; explain correction without rewriting the original source |
| NEEDS_REVIEW | overall_level=null, level=null; six scores may be null | Non-strict audit only; review_notes identify missing evidence; needs_human_review=true |
| REJECTED | L0, level=0; six scores may be null | Non-strict audit only; controlled rejection_reason plus explanatory review_notes |

L0 means rejected **if and only if** review_status is REJECTED. Pure concepts, simple questions and lack of calculus are not rejection reasons. Use the exact six rejection codes in rubric §3.1. Confirm a duplicate and its canonical ID before using DUPLICATE_NO_ADDED_VALUE.

For incomplete/rejected audits keep unknown results null and arrays empty. Any numerical TIMBAD score still requires evidence/rationale. A tentative REVISE rating requires the same reliable solution and scoring evidence as APPROVED. Non-approved records need review_notes. Separately keep `classification.status: "review"`, `classification.review.reviewed: false`, and appropriate question review_reasons for unresolved cases. Strict validation blocks them independently of numeric difficulty.

Default multipart treatment is a separate assessment for each requested part (separate question records when independently published). If the original multipart question is retained as one record, keep per-part audits under `difficulty.part_ratings` (each with `part_id` and its own complete rating fields), and justify the aggregate in overall_reason. Highest substantive demand is the baseline; quantity of parts does not raise L. The current validator checks the aggregate contract only; a reviewer must inspect each part and any cross-part dependency before approving.

## Compatibility and migration

- `classification.difficulty` is canonical. `level` must match `overall_level` exactly.
- `derive_semantic_tags.py` derives top-level numeric `difficulty: 1..7` and `difficulty:N` only for APPROVED ratings. For rejected/pending records the top-level mirror is null and no difficulty tag is emitted. L0 remains only in the audit, so it cannot become the easiest practice tier.
- Existing records containing only `level: 1..5` and `drivers` are legacy. Non-strict semantic validation accepts their old contract for inspection; **strict validation requires fresh TIMBAD reassessment**. Do not multiply, stretch, clamp, or reuse a legacy number as a new L without reevaluating the full question.
- Keep an old assessment in a bank's assessment-history metadata when needed for traceability; this is question review history, not a duplicate installed skill.
- Run derive_semantic_tags.py after reassessment, then the full strict bank/semantic gates from SKILL.md. Difficulty validation is integrated into validate_semantic_classification.py. Run it alongside validate_bank.py, as required by the existing final hard gate; no new separate command is required.
- New numeric 6/7 mirrors require compatible downstream consumers. Do not silently map to a legacy five-tier website. This skill update does not migrate an existing website, republish banks or re-rate existing questions.

The validator checks types, required evidence, states and mirror consistency. It cannot certify physical correctness, whether an insight is substantive, or whether the grader truly solved first. Those require the source-backed model/human review, the full rubric and calibration.
