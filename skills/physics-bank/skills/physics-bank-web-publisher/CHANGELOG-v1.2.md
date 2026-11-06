# v1.2.0 — Production AI publisher API

- Add a direct production API workflow for AI publishing; no browser upload clicks are required.
- Upload compiled bundles and content-addressed images through time-limited Supabase Storage links.
- Add a database change plan, atomic versioned publish, private API token handling, and post-publish version verification.
- Keep preview publishing on the authenticated administrator workflow.
- Use production-scoped asset paths and record file size metadata for server-side integrity checks.

## 1.2.0-rc.2 — Required dual-surface verification

- Requires separate live verification for the Practice library and Topic Practice after publication.
- Checks course-subtopic question IDs/counts and canonical primary-knowledge-UID question IDs/counts against the publish bundle.
- Records PASS, FAIL, or BLOCKED_AUTH independently; authentication or entitlement gaps remain unverified.
- No runtime schema, permissions, or production data changes.

