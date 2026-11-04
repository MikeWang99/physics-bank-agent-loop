# physics-bank v2.2.0

- Added a first-class visual-choice asset pipeline.
- Final choice images now live under `assets/choices/<question-id>/`.
- Added `choices[].asset_ids`, `choice_index`, and `crop.isolated_choice` contracts.
- Added `organize_choice_assets.py` for canonical paths and deterministic JSON binding.
- Strict validation now rejects combined/unisolated option images, wrong folders, shared choice assets, duplicate choice slots/files, and broken choice bindings.
- Kept top-level `question.asset_ids` for downstream compatibility.
