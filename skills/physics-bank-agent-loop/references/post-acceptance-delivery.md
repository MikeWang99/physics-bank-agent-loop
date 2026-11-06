# Post-acceptance delivery contract (v1)

This phase **starts only after** the existing Coordinator/Creator/independent Reviewer loop has finished. Never change or silently rerun the source extraction, wording, source images, crop seals, narrative layout, knowledge tree, or original answer provenance just to make a question publishable.

## Immutable inputs and two queues

Input: an accepted canonical \`question-bank/\` folder, a normal \`pocket-cosmos-publish-config/v1\` config, and \`physics-bank-delivery-answers/v1\` reviewed answers. The postprocessor must **not** write \`questions.json\`, \`assets.json\` or any original asset. Output is a publisher-compatible JSON bundle plus a local audit queue.

- **Ready to publish:** valid question with a source-faithful image/text presentation, allowed existing course, reviewed knowledge UID and difficulty, and independently checked standardized answer. These become live practice questions and are also normal-priority, *not-yet-human-reviewed* items.
- **High-priority intervention:** missing/invalid UID, course mismatch, unresolved image or reading-order problem, unsupported layout, source/AI answer disagreement, incomplete answer verification, or a compile failure. Keep its original ID and error in \`delivery-review-queue.json\`. Do not invent a UID or change a source symbol. These are **not** sent to the production publisher. A future admin intake endpoint must persist them in a high-priority queue independent from the published-version review list; the local queue alone is not that feature.

A failed question must not block other valid questions in the same accepted bank. Re-running with fixed inputs is deterministic and safe. Existing website publisher API already deduplicates identical content hashes and retains immutable revisions.

## Answer writer / independent answer verifier

The source PhysicsBank remains authoritative for original answer provenance. Its rule "do not synthesize an official answer" stays unchanged. **Only the post-acceptance delivery layer** may generate a student-facing explanation. It must mark its origin \`ai_generated\` or \`ai_enhanced\`, never \`official\`.

Use two independent agent passes. The verifier gets the question/source images and the proposed final answer, but should solve independently before seeing the writer's derivation. It explicitly checks numerical values, units, model assumptions, MCQ option and image identity, any official key, FRQ grading clarity and LaTeX. A rejected/inconclusive answer goes to high-priority intervention; it is never auto-published. Both review identities must be nonempty and distinct, and verification must include concrete notes, not just a boolean.

Answer file example:

\`\`\`json
{
  "schema": "physics-bank-delivery-answers/v1",
  "questions": [
    {
      "id": "ap1-q001",
      "kind": "mcq",
      "correct_labels": ["B"],
      "detailed_explanation": "Start from $\\sum F=ma$ and check the stated direction.",
      "creator": {"id": "answer-writer"},
      "reviewer": {"id": "independent-answer-verifier", "independent": true, "verdict": "ACCEPT", "notes": "Re-solved from the original diagram; agrees with B and has consistent units."}
    },
    {
      "id": "ap1-q002",
      "kind": "frq",
      "exam_answer": "State $\\sum F=ma$, substitute the given values, and report the result with units.",
      "detailed_explanation": "Define the system, draw a force diagram, explain the coordinate choice, and then derive the acceleration.",
      "creator": {"id": "answer-writer"},
      "reviewer": {"id": "independent-answer-verifier", "independent": true, "verdict": "ACCEPT", "notes": "Independent derivation and unit check completed."}
    }
  ]
}
\`\`\`

Use source-provided \`g\` when specified; otherwise, for user-created solutions, default to \`g=10\,\mathrm{m/s^2}\`. Do not override an official marking scheme or source-defined convention. Use \`$...$\` and \`$$...$$\` exclusively for mathematics, explicit units, short paragraphs, aligned equations where useful, and no raw HTML. MCQ outputs label plus detailed reasoning. FRQ outputs first a concise, full-credit **Exam-style answer**, then a distinct **Detailed explanation** suitable for teaching; avoid extraneous filler.

The postprocessor overlays \`version.answer.solution\` and \`metadata.practiceStep.solution\`, records \`metadata.physicsBank.deliveryAnswer\`, and recomputes the exact publisher content hash. It does not overwrite the original \`metadata.physicsBank.answer\`. A human change via website review should continue creating a fresh version with the existing versioning model.

## Run

From the Agent Loop repository root, after the canonical existing loop returns ACCEPT:

\`\`\`sh
python3 skills/physics-bank-agent-loop/scripts/delivery.py \
  /path/to/question-bank /path/to/publish-config.json \
  /path/to/independently-reviewed-answers.json \
  --output-dir /path/to/question-bank/delivery
\`\`\`

This default is a **local preflight only**; it does not contact production. Inspect \`delivery-review-queue.json\` and the validated ready bundle. With an explicitly authorized publication task and configured publisher token, append \`--source-accepted --apply\` after the original full-bank Reviewer returns ACCEPT to invoke the existing \`publish_via_api.py\`. Never put \`PHYSICS_BANK_PUBLISH_TOKEN\` or Supabase service keys into generated bundles or GitHub.

### Important website integration limitations

Current Pocket Cosmos already has \`/api/ai/physics-bank/imports\`, \`/api/practice/sets/:id\`, \`/api/topic-practice/questions\`, \`/api/admin/banks?mode=review\`, and immutable question-version tables.

The topic index requires more than a matching UUID: v2 classification status, reviewed flag, taxonomy SHA, approved or appropriately unrated difficulty, source-system equality and course entitlement must agree. A previously uploaded item that does not meet those gates can appear in the Practice set but not Topic Practice. Diagnose these exact predicates first; never mutate the pinned taxonomy.

Practice and Topic Practice use different mappings. The Practice course tree filters by the course subtopic in `practiceStep.curriculum.primarySubtopicId`; unified Topic Practice filters by the canonical taxonomy value in `physicsBank.classification.primary_knowledge_uid`, mirrored by `physicsBank.primaryKnowledgeUid` and `practiceStep.primaryKnowledgeUid`. The publisher's UID, taxonomy hash, course projection node ID and primary subtopic must agree with the reviewed bank. A unique question ID identifies the question; it is not a knowledge-tree UID.

For a requested production release, verify both routes separately after publish. Compare the Practice catalog paths and per-subtopic question IDs/counts with the bundle. For Topic Practice, call the authorized topic-question API once for every mapped primary UID and compare the returned question IDs/counts; then visually open representative mapped nodes in an entitled signed-in session. Record the two route results separately. If authentication or entitlement is unavailable, mark that route unverified and report “published; authenticated placement unverified”; a 401/403 or sign-in screen cannot be counted as successful UI verification.

The cloud review editor currently blocks v2/TIMBAD edits. Website repair requires a separate migration/API/UI change to preserve provenance and create immutable versions. Do not describe the local report as a finished web review queue, or claim the website has been updated just because this skill generated a bundle.

## P2 (design only, not implemented)

Two separate **submission adapters**, one from Codex and one from the owner-only web admin UI, should upload PDF, DOCX, PNG/JPEG/WebP, scans or mixed inputs to private object storage and enqueue the *same* Coordinator job. The job selects an input parser but shares the exact current PhysicsBank Creator and independent Reviewer. A server-side worker, not the Vercel request handler and not a browser-held token, controls model execution, retries, quotas and progress. Track job ID, per-question ID/status, user scope, source hashes and idempotency keys. Enforce authorization, MIME/content validation, malware/size limits and private storage. Preserve source copyrights and rights to publish. This second stage does not exist in v1.


## Partial source acceptance when a whole batch fails

The original Reviewer remains strictly read-only and its whole-bank \`ACCEPT\` gate **is not relaxed**. When a batch cannot be accepted after five repair rounds, the Coordinator may ask the same independent Reviewer to separately audit each unaffected question as an isolated source unit against its original pages, relevant asset seals and strict original PhysicsBank validators. Only independently ACCEPTed units can be published. The Coordinator records every unit's source evidence and a SHA-256 of the original *unchanged* \`questions.json\`, e.g.:

\`\`\`json
{
  "schema": "physics-bank-source-acceptance/v1",
  "sourceQuestionsSha256": "<sha256 of original questions.json bytes>",
  "reviewerId": "independent-source-reviewer",
  "reviews": [
    {"questionId": "q001", "disposition": "ACCEPT", "evidence": "Compared source P2 Q1, diagram seals and strict unit validators."},
    {"questionId": "q002", "disposition": "REVISE", "evidence": "Source diagram unclear on P3 Q2."}
  ]
}
\`\`\`

Supply the optional \`--acceptance-report /path/to/acceptance.json\` to \`delivery.py\`. This report also satisfies the source acceptance gate for \`--apply\`; a fully accepted original bank instead requires \`--source-accepted --apply\`. It rejects changed source-bank SHA, missing evidence, unknown IDs or missing dispositions. Unaccepted questions are added to the high-priority unpublished queue while individually accepted questions continue toward compilation. Without a per-question report, call the adapter only on a whole bank that the original Reviewer has already accepted. Merely splitting a failing bank **must not** turn a failed question into an accepted one. This partial-review protocol does not grant permission to skip source-fidelity checks.
