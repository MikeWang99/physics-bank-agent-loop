# Math normalization contract · v2.6

The canonical student-facing text in `questions.json` uses `markdown+latex`.

## Purpose

PDF text extraction preserves source evidence, but PDF text layers often flatten mathematical typography. A visually typeset subscript may arrive as:

```text
U_K
v_0
mu_s
\mu_s
x^2
```

Stage A must keep the raw extraction for audit. Stage B must compare the rendered source page and normalize mathematical notation into explicit Markdown/LaTeX delimiters.

Examples:

```text
U_K       → $U_K$ or $U_{K}$
v_0       → $v_0$
mu_s      → $\mu_s$
\mu_s     → $\mu_s$
F_net     → $F_{\text{net}}$
x^2       → $x^2$
\frac{1}{2}mv^2 → $\frac{1}{2}mv^2$
```

The exact symbol must follow the source page. Do not infer a different variable merely because it is physically plausible.

## What must be inside math delimiters

Any student-facing text that uses LaTeX syntax must place that syntax inside `$...$` or `$$...$$`.

In particular, do not publish bare:

- underscore subscripts such as `U_K`, `v_0`, `F_net`;
- caret superscripts such as `x^2`, `10^3`;
- LaTeX commands such as `\mu`, `\theta`, `\frac`, `\Delta`.

Plain prose, ordinary numbers, units, and single letters are not automatically rejected. The hard gate intentionally targets unmistakable math-markup leakage rather than guessing every possible mathematical token.

## Review workflow

1. Preserve the Stage A raw source text unchanged.
2. Inspect the source page wherever mathematical typography may have been flattened.
3. Normalize only notation/whitespace needed to encode the same source meaning.
4. Keep prose wording and physical conditions unchanged.
5. Run the math validator.
6. If the source symbol itself is uncertain, keep `requires_manual_review: true` rather than guessing.

## Hard gate

Focused diagnostic:

```bash
python scripts/validate_math_markup.py question-bank/questions.json
```

The normal strict `validate_bank.py` gate also runs the same check.

The validator rejects student-facing canonical text containing:

- bare subscript/superscript syntax outside math delimiters;
- bare LaTeX commands outside math delimiters;
- unmatched dollar math delimiters.

Code spans and URLs are ignored so identifiers documented as literal code are not mistaken for physics notation.

## Downstream contract

Downstream renderers must not guess that every underscore is a subscript. They should consume the canonical math delimiters. This prevents prose identifiers from being silently reformatted and keeps PDF/web rendering deterministic.
