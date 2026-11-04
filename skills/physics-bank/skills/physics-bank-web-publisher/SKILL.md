---
name: physics-bank-web-publisher
description: Compile a validated physics-bank bundle into the Pocket Cosmos practice runtime schema, publish immutable question versions and content-addressed assets to Supabase, and verify the live website without discarding physics-bank provenance, classification, or layout information.
---

# Physics Bank Web Publisher v1.2

Publish a finished `physics-bank` question bank into Pocket Cosmos. This is a **compiler/publisher**, not another extraction pipeline.

The source of truth before publication is the validated physics-bank bundle. The source of truth after publication is Pocket Cosmos Supabase:

```text
physics-bank
→ compile
→ validate
→ production API plan
→ direct signed asset upload
→ atomic API publish
→ verify database result and live runtime
```

## Target architecture

Pocket Cosmos production currently uses:

- Vercel project: `pocket-cosmos-online`
- production site: `https://www.pocket-cosmos.com`
- Supabase project ref: `bnnxjqdwvzbkjbjfkofs`
- database identity table: `public.questions`
- immutable content versions: `public.question_versions`
- version-bound assets: `public.question_assets`
- private asset bucket: `question-assets`

Do not put new bank images back into GitHub/Vercel static asset folders.

Read before execution:

- `references/pocket-cosmos-runtime-schema.md`
- `references/publish-config.md`
- `references/storage-contract.md`
- the parent physics-bank `SKILL.md`, especially semantic classification and narrative-layout requirements

## Required input

A completed physics-bank directory containing at minimum:

```text
question-bank/
  questions.json
  assets.json
  classification-taxonomy.json
  assets/
    figures/
    choices/
```

and a publisher config using `pocket-cosmos-publish-config/v1`.

## Gate 1 — validate the source bank

Run the parent physics-bank validators first. Never publish a bank that fails text, year, visual, layout, or semantic validation.

Typical commands from the repository root:

```bash
python scripts/validate_bank.py <bank>/questions.json \
  --assets <bank>/assets.json --strict --require-text-review

python scripts/validate_year_metadata.py <bank>/questions.json

python scripts/validate_semantic_classification.py <bank>/questions.json \
  --taxonomy <bank>/classification-taxonomy.json --strict
```

## Gate 2 — compile, do not copy

Run:

```bash
python skills/physics-bank-web-publisher/scripts/compile_publish_bundle.py \
  <bank> <publish-config.json> \
  --output <bank>/web-publish-bundle.json
```

The compiler maps the canonical bank into the current website runtime contract while preserving the full future-facing information under `question_versions.metadata.physicsBank`.

Important mappings:

- stable web question ID: `<practice-set-id>::<physics-bank-question-id>`
- `questions.legacy_question_id`: physics-bank question ID
- `question_versions.stem`: `context + stem` so current UI remains self-contained
- `practiceStep.prompt`: same self-contained display prompt
- physics-bank `classification` → `metadata.physicsBank.classification`
- physics-bank `difficulty` → `practiceStep.difficulty`
- key-only `answer.label` → `practiceStep.correctAnswer` with **no generated** `solution` or official-key boilerplate
- authentic `answer.text` → `practiceStep.solution` only when source actually provides worked reasoning
- source-reviewed answer figures → version-bound `question_assets.role=answer` (`solutionImage` for the first, archival `answerAssets` for additional diagrams)
- complete answer layout/provenance → `metadata.physicsBank.answer`
- readable topic/difficulty tags first; machine semantic tags are preserved after them
- choice assets → `question_assets.role=choice` + `choice_key`
- first compatible narrative figure → `role=stem, metadata.slot=image`
- later compatible figures → `role=figure, metadata.slot=supportingImages`

## Narrative-layout compatibility — hard gate

The current Pocket Cosmos Practice UI renders:

```text
prompt
→ main image
→ supporting images
→ choices
```

It does **not** currently render arbitrary `layout_blocks`.

Therefore a physics-bank question is web-compatible only when all narrative text appears before all stem/shared figures. If the bank contains:

```text
figure → text
text → figure → text
figure → text → figure
```

or any other interleaving, publishing is blocked by default.

This protects questions such as multi-image FRQs from silently losing the image positions that physics-bank deliberately preserved.

An explicit config override `rendering.allow_layout_degradation=true` may compile such a question for temporary use. The full `layoutBlocks` still remains in `metadata.physicsBank`, and the publish bundle must mark `renderCompatibility.status=degraded`.

Never silently downgrade layout fidelity.

### Worked-answer layout gate

The current Practice frontend supports a single `solutionImage`, but not arbitrary alternating solution text/figures. Publisher v1.1 preserves the full source-derived `answer.layout_blocks` and all answer assets under `metadata.physicsBank.answer` / version-bound `question_assets`.

If an answer contains multiple solution figures or any explanation text after a solution figure, **block publication by default**. The optional `rendering.allow_answer_layout_degradation=true` flag explicitly permits a degraded display while retaining all source content in the database. This must never be silently enabled.

For a key-only source, do not synthesize `Official answer: A.`; only emit `correctAnswer` when an option is established. Leave `practiceStep.solution` absent.

## Gate 3 — validate the publish bundle

Run:

```bash
python skills/physics-bank-web-publisher/scripts/validate_publish_bundle.py \
  <bank>/web-publish-bundle.json --bank-root <bank>
```

This checks stable IDs, unique positions, content hashes, asset hashes/paths, current runtime metadata, choice bindings, and layout compatibility.

## Default AI publication workflow

Use the authenticated production API for publishing. Do not simulate clicks in the human upload page and do not send a Supabase service-role key from the AI environment.

The API is https://www.pocket-cosmos.com/api/ai/physics-bank/imports. The publisher token is read from PHYSICS_BANK_PUBLISH_TOKEN or ~/.codex/secrets/physics-bank-publisher.env. Keep it private and never print it.

The script publish_via_api.py uploads the compiled JSON and image bytes directly to short-lived Supabase Storage upload links. The website API validates the bundle and image hashes, returns a database change plan, then commits all question versions and catalog updates atomically when --apply is supplied.

Plan first:

    python ~/.codex/skills/physics-bank/skills/physics-bank-web-publisher/scripts/publish_via_api.py <bank>/web-publish-bundle.json --bank-root <bank>

Only use --apply after the user asked to publish:

    python ~/.codex/skills/physics-bank/skills/physics-bank-web-publisher/scripts/publish_via_api.py <bank>/web-publish-bundle.json --bank-root <bank> --apply

The plan-only command removes its temporary private manifest after returning the plan. It does not upload question images or write question records. The --apply command uploads images concurrently, verifies their bytes server-side, publishes in one transaction, and confirms that every question is at its current version.

The endpoint is production-only. Preview content must continue through the administrator workflow so preview and production question data remain isolated.

## Manual database fallback — only if the API is unavailable

Prefer the production API above. Use the service-role database scripts below only for an explicitly requested manual recovery or while the API is unavailable.

Default behavior is planning only. Do not write production merely because compilation succeeded.

Create the read-only diff:

```bash
python skills/physics-bank-web-publisher/scripts/plan_publish.py \
  <bank>/web-publish-bundle.json \
  --output <bank>/web-publish-plan.json
```

It requires server-side `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` but performs no writes.

A publish plan must state for every question:

- stable question ID
- desired content hash
- whether the hash already exists
- new version required or no-op
- asset paths to upload
- render compatibility

Content hashes deliberately exclude signed URLs, database UUIDs, and timestamps.

### Manual asset upload

Storage paths are immutable and content-addressed:

```text
question-assets/
  banks/production/assets/<practice-set-id>/<asset-id>-<sha12>.<ext>
```

Upload before DB mutation:

```bash
python skills/physics-bank-web-publisher/scripts/upload_assets.py \
  <bank>/web-publish-bundle.json --bank-root <bank> --apply
```

The script requires server-side credentials:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Never expose the service-role key to browser/client code or commit it to Git.

Uploads use `x-upsert: false`. A changed file receives a new hash-derived path instead of overwriting CDN content.

### Manual atomic DB apply

After every required asset upload succeeds, generate the transaction:

```bash
python skills/physics-bank-web-publisher/scripts/build_transaction_sql.py \
  <bank>/web-publish-bundle.json \
  --output <bank>/web-publish.sql
```

When the Supabase connector is available, execute the generated SQL against project `bnnxjqdwvzbkjbjfkofs` as **one transaction**.

The SQL:

1. upserts stable `questions` identities/positions;
2. reuses an existing `question_versions` row when `question_id + content_hash` already exists;
3. otherwise appends `max(version)+1`;
4. inserts version-bound `question_assets`;
5. never overwrites or deletes historical question versions.

Do not retire questions missing from a new bundle unless the user explicitly requests retirement.

## Verification

After apply:

1. The API response must report allQuestionsCurrent=true and a question count matching the bundle. Only for a manual database fallback, verify DB identities, expected content hashes, and asset rows:

   ```bash
   python skills/physics-bank-web-publisher/scripts/verify_database.py \
     <bank>/web-publish-bundle.json
   ```

2. verify `/api/practice/catalog` contains the new/updated set;
3. fetch `/api/practice/sets/<practice-set-id>` and verify question IDs/count/order and non-null `questionVersionId`:

   ```bash
   python skills/physics-bank-web-publisher/scripts/verify_published_set.py \
     <bank>/web-publish-bundle.json
   ```

4. confirm choice images and stem/supporting images resolve;
5. when browser access and permissions allow, visually inspect representative questions, including:
   - text-only question;
   - stem-figure question;
   - visual-choice question;
   - multi-figure question.

For locked practice sets, a 403 from the public API is not evidence of failed publication. Use the successful API response's database verification instead; do not request a Supabase service-role key in the AI environment.

## Versioning rules

`questions.id` is stable identity. `question_versions` is immutable history.

- same canonical content hash → no new version
- changed text/answer/classification/layout/asset hash/runtime mapping → new version
- changed signed URL/timestamp/UUID → must **not** create a new version
- asset bytes change → asset storage path changes because SHA changes

## What this Skill never does

- does not re-OCR or repair source questions;
- does not reclassify physics content;
- does not guess missing images;
- does not discard `classification`, `layout_blocks`, provenance, or source pages;
- does not modify student attempts/assignments;
- does not alter practice permissions;
- does not silently publish layout-degraded questions;
- does not delete historical versions.
