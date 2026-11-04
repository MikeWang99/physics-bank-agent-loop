# v2.4.0 — Visual completeness gate

- Discovery candidates now absorb nearby short text labels around vector/raster graphics, preventing labels such as voltage values or Greek symbols from being silently dropped by the first crop.
- Added `render_source_asset.py`: final stem/shared pixels are rendered directly from the original PDF source bbox instead of from a lossy discovery candidate.
- Added source-halo review previews so the kept bbox is inspected in page context.
- Added `seal_asset_review.py`: reviewed assets are bound to the exact final-image SHA-256, source-PDF SHA-256, and reviewed source bbox.
- Destructive recropping now invalidates existing visual-review seals automatically.
- Strict validation now detects stale review seals, ink touching crop borders, source objects crossing the bbox, and likely short diagram labels just outside the bbox.
- Added regression tests reproducing the “diagram body present but side label omitted” failure class.
- Added GitHub Actions CI for the full unit-test suite.
