# v2.5.0 — Auditable semantic classification

- Added a mandatory semantic-classification stage after complete text/visual reconstruction
- Added bank-level `classification-taxonomy.json` so course → unit → topic → subtopic IDs are stable instead of model-invented per question
- Added canonical `physics-question-classification/v1` with curriculum mapping, physics domain, primary/secondary topics, knowledge points, solution models, controlled skills, difficulty, evidence, confidence, and review status
- Added `references/semantic-taxonomy.json` with controlled domains, solution-model kinds, skills, a 1–5 difficulty rubric, and a confidence review threshold
- Added `derive_semantic_tags.py` so flat compatibility fields and searchable semantic tags are generated from canonical classification rather than manually authored
- Curriculum tags use stable taxonomy IDs, e.g. `unit:dynamics` and `topic:newtons-laws`
- Added `validate_semantic_classification.py` hard gate for taxonomy resolution, parent-child consistency, evidence, controlled vocabulary, primary solution models, difficulty, confidence, mirrors, and stale/missing tags
- Stage A now explicitly marks `classification: null` so extraction cannot be confused with semantic enrichment
- Added regression coverage for unknown topics, missing evidence, low confidence, invalid skills, missing primary models, stale mirrors/tags, and duplicate mappings
- Preserved all v2.4 source-fidelity, visual-completeness, review-seal, and narrative-layout gates
