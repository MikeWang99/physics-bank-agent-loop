# Changelog

## 3.0.0-rc.1 — 2026-10-26 (feature branch, NOT production)

- Based on main 6338dbb3d7000b1fa3b3842825374de5e4de298f with VERSION=2.9.0;
  Git tag v2.9.0 was not present at audit time.
- Adds classification schema v2, one canonical primary knowledge UID and explicit
  source_system / source_event. Optional new source year, no mandatory year tag.
- Pins 936 website nodes by website commit/Git blob identity and provides
  verified source sync + candidate lookup, strict independent-review audit gates.
- Keeps entire TIMBAD L1-L7 validator and six dimensions unmodified.
- Keeps extraction/answer/visual/PDF source verification and original question IDs.
- Existing v1 semantic classifier, tags and bank taxonomy remain valid for old banks.
- Publisher candidate v1.2.0-rc.1 carries source+UID, keeps full audit metadata,
  refuses unreviewed/missing UID and retains immutable version logic.
- Companion website development PR required before launch. No production writes.
- Accuracy still requires educator-labeled Gold Standard evaluation; no numeric
  classification accuracy claimed. See references/knowledge-classification-v2.md.
