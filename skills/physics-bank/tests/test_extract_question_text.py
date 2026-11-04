#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("extract_question_text", ROOT / "scripts" / "extract_question_text.py")
MOD = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = MOD; SPEC.loader.exec_module(MOD)


def make_pdf(path: Path, pages: list[list[str]]):
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((72, y), line, fontsize=11)
            y += 18
    doc.save(path)


class ExtractTests(unittest.TestCase):
    def test_shared_context_and_cross_page_continuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "exam.pdf"
            make_pdf(pdf, [[
                "Questions 1 and 2 refer to the following information.",
                "A block slides on a rough horizontal surface.",
                "1. Explain the direction of friction.",
            ], [
                "This sentence continues question 1 on the next page.",
                "2. Which quantity is conserved?",
                "A. Momentum", "B. Energy", "C. Charge", "D. None",
            ]])
            result = MOD.extract(pdf, "exam")
            self.assertEqual(result["question_count"], 2)
            q1, q2 = result["questions"]
            self.assertIsNone(q1["classification"])
            self.assertIsNone(q2["classification"])
            self.assertIn("Questions 1 and 2", q1["context"])
            self.assertIn("Questions 1 and 2", q2["context"])
            self.assertEqual(q1["source_pages"], [1, 2])
            self.assertIn("continues question 1", q1["stem"])
            self.assertEqual([c["label"] for c in q2["choices"]], ["A", "B", "C", "D"])

    def test_shared_context_between_questions_is_not_swallowed_by_previous_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "exam.pdf"
            make_pdf(pdf, [[
                "4. What is the acceleration?",
                "A. 1 m/s^2", "B. 2 m/s^2",
                "Questions 5 and 6 refer to the following diagram and information.",
                "A cart collides with a stationary cart.",
                "5. What is the total momentum?",
                "6. Is kinetic energy conserved?",
            ]])
            result = MOD.extract(pdf, "exam")
            self.assertEqual(result["question_count"], 3)
            q4, q5, q6 = result["questions"]
            self.assertNotIn("Questions 5 and 6", q4["raw_source_text"])
            self.assertIn("Questions 5 and 6", q5["context"])
            self.assertIn("A cart collides", q5["context"])
            self.assertEqual(q5["context"], q6["context"])

    def test_question_number_variants(self):
        self.assertEqual(MOD.question_anchor("Question 12: Find the speed")[0], "12")
        self.assertEqual(MOD.question_anchor("Q7. Select one")[0], "7")
        self.assertEqual(MOD.question_anchor("3) Calculate")[0], "3")


if __name__ == "__main__":
    unittest.main()
