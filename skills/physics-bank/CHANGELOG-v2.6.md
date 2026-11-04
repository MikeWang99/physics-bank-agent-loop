# v2.6.0 — Canonical math normalization

- Added a mandatory Stage B math-normalization contract for student-facing canonical text
- Added `references/math-normalization.md` with source-faithful examples and review rules
- Added `validate_math_markup.py` focused diagnostics
- Strict `validate_bank.py` now rejects bare underscore subscripts, caret superscripts, LaTeX commands, and unmatched dollar delimiters outside `$...$` / `$$...$$`
- Stage A raw extraction remains untouched; normalization happens only after source-page comparison
- Code spans and URLs are ignored by the bare-math detector to reduce false positives
- Added regression tests for `U_K`, `v_0`, `x^2`, `\mu_s`, valid inline/display math, unmatched delimiters, and choice text
- Updated schema/text-extraction docs and skill entrypoint
