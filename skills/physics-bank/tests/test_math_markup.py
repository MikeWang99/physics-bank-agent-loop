#!/usr/bin/env python3
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("validate_bank_math", ROOT / "scripts" / "validate_bank.py")
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["validate_bank_math"] = MOD
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class MathMarkupTests(unittest.TestCase):
    def test_bare_subscript_is_detected(self):
        self.assertIn("U_K", MOD.find_bare_math_markup("The energy is U_K."))

    def test_bare_superscript_is_detected(self):
        self.assertIn("x^2", MOD.find_bare_math_markup("Use x^2 in the expression."))

    def test_bare_latex_command_is_detected(self):
        found = MOD.find_bare_math_markup(r"The coefficient is \mu_s.")
        self.assertTrue(any(token.startswith("\\mu") for token in found), found)

    def test_inline_math_is_not_flagged(self):
        text = r"The energy is $U_K$, the speed is $v_0$, and $x^2$ is used with $\mu_s$."
        self.assertEqual(MOD.find_bare_math_markup(text), [])

    def test_display_math_is_not_flagged(self):
        self.assertEqual(MOD.find_bare_math_markup(r"Use $$E=\frac{1}{2}mv^2$$."), [])

    def test_code_and_url_are_ignored(self):
        text = "Literal code " + chr(96) + "student_id" + chr(96) + " is documented at https://example.com/a_b."
        self.assertEqual(MOD.find_bare_math_markup(text), [])

    def test_unmatched_dollar_is_detected(self):
        self.assertIn("<unmatched-$>", MOD.find_bare_math_markup("Use $v_0 here."))

    def test_question_reports_choice_location(self):
        q = {
            "id": "q1",
            "stem": r"Use $v_0$.",
            "choices": [{"label": "A", "text": "U_K"}, {"label": "B", "text": r"$U_K$"}],
        }
        issues = MOD.question_math_issues(q)
        self.assertEqual(len(issues), 1)
        self.assertIn("choice[A]", issues[0])
        self.assertIn("U_K", issues[0])

    def test_strict_bank_validation_rejects_bare_math(self):
        q = {
            "id": "q1",
            "content_format": "markdown+latex",
            "context": "",
            "stem": "Find U_K.",
            "choices": [],
            "answer": {"text": None, "label": None, "evidence": "not-provided"},
            "source_pages": [1],
            "extraction": {"text_reviewed": True},
            "asset_ids": [],
            "requires_manual_review": False,
            "review_reasons": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.json"
            assets = root / "assets.json"
            questions.write_text(json.dumps({"questions": [q]}), encoding="utf-8")
            assets.write_text(json.dumps({"assets": []}), encoding="utf-8")
            result = MOD.validate(questions, assets, strict=True, require_text_review=True)
        self.assertTrue(any("bare/unbalanced math markup" in e for e in result["errors"]), result["errors"])


if __name__ == "__main__":
    unittest.main()
