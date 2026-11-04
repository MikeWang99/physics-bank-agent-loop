# v1.2.0 — Production AI publisher API

- Add a direct production API workflow for AI publishing; no browser upload clicks are required.
- Upload compiled bundles and content-addressed images through time-limited Supabase Storage links.
- Add a database change plan, atomic versioned publish, private API token handling, and post-publish version verification.
- Keep preview publishing on the authenticated administrator workflow.
- Use production-scoped asset paths and record file size metadata for server-side integrity checks.
