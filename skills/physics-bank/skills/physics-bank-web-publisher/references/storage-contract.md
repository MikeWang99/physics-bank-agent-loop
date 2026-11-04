# Storage and versioning contract

## Buckets

Current production buckets relevant to this Skill:

- `question-assets` — private runtime question media
- `source-documents` — private source-document bucket, currently separate from runtime assets

v1.0 publishes question figures/choice images only to `question-assets`.

## Immutable content-addressed object path

```text
banks/production/assets/<practice-set-id>/<asset-id>-<sha256-prefix>.<ext>
```

Example:

```text
banks/production/assets/fma-competition-bank/fma-2024-q017-choice-a-01-91c3d5f8e1af.png
```

Do not overwrite a changed file at the old path. Supabase recommends new object paths rather than overwriting CDN-cached assets.

## Upload sequence

1. compile + validate bundle;
2. calculate/verify every asset SHA-256;
3. request time-limited upload links from the production API;
4. upload the bundle and missing content-addressed objects directly to their signed URLs with HTTP `PUT` and `x-upsert: false`;
5. only after all uploads succeed, ask the API to execute the database transaction.

An upload failure must stop DB publication.

## Credentials

The AI publisher token is stored outside the repository in ~/.codex/secrets/physics-bank-publisher.env. PHYSICS_BANK_PUBLISH_TOKEN may override that file for one process.

The website's SUPABASE_SERVICE_ROLE_KEY remains server-side. The publisher script never reads or sends that database key.

## Database mutation sequence

The production API applies database rows in one transaction after storage succeeds.

Historical `question_versions` are immutable.

A version is reused when:

```text
question_id + content_hash
```

already exists.

A new version is appended only when the canonical publish content changes.

## Orphans

If storage succeeds but the SQL transaction fails, content-addressed orphan objects are safe and may be reused by the retry. Do not delete them automatically during a failed publish.
