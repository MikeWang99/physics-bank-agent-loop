#!/usr/bin/env python3
"""Regressions for student-facing source fidelity in the PhysicsBank gate."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_bank.py"
spec = importlib.util.spec_from_file_location("validate_bank", SCRIPT)
bank = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bank)


class StudentSourceFidelityTests(unittest.TestCase):
    def question(self, stem, original="", figure=None):
        extraction = {"raw_source_text": original}
        if figure:
            extraction["source_layout_evidence"] = {
                "figure_evidence": {"id": figure, "source_page": 125},
            }
        return {"id": "q-test", "context": "", "stem": stem, "extraction": extraction}

    def test_source_figure_number_and_description_never_enter_student_stem(self):
        for stem in (
            "Source figure description (Fig. 4–58, p. 104): mower pushes down.",
            "See Fig. 4–59 and determine the acceleration.",
            "The pulley is shown in Figure 4-53.",
            "Source-derived diagram description: the arrow points left.",
            "Source figure description (Fig. 4–59, PDF p.125 / printed p.104).",
        ):
            with self.subTest(stem=stem):
                problems = bank.student_source_fidelity_issues(
                    self.question(stem, original="a force diagram is given", figure="Fig. 4-58"), ["fig-own"]
                )
                self.assertTrue(any("student-facing text" in error for error in problems), problems)

    def test_own_figure_is_required_when_original_uses_numbered_figure(self):
        original = "Determine the forces in Fig. 4–58."
        q = self.question("Determine the forces in the diagram.", original)
        self.assertTrue(any("no owned stem/shared figure" in e for e in
                            bank.student_source_fidelity_issues(q, [])))
        self.assertEqual(bank.student_source_fidelity_issues(q, ["fig-own"]), [])

    def test_uncroppable_overlapping_figure_is_a_review_blocker_not_a_text_substitute(self):
        q = self.question("A block is on a smooth incline.", "The block shown in Fig. 4–59 has mass 7 kg.",
                          figure="Fig. 4–59")
        self.assertTrue(any("no owned stem/shared figure" in e for e in
                            bank.student_source_fidelity_issues(q, [])))

    def test_unverified_ignore_friction_is_rejected_even_when_original_is_smooth(self):
        q = self.question(
            "[Ignore friction.] A box moves down a smooth slope.",
            "A box moves down a smooth slope."
        )
        self.assertTrue(any("unverified physical assumption" in e for e in
                            bank.student_source_fidelity_issues(q, [])))

    def test_verified_section_heading_allows_shared_ignore_friction(self):
        # Giancoli Global Edition 7e, printed p. 102 / PDF p. 123:
        # "4-7 Newton's Laws and Vectors [Ignore friction.]"
        q = self.question("Assume friction is negligible. A rope lifts a box.",
                          "A rope lifts a box.")
        q["extraction"]["shared_source_instructions"] = [{
            "text": "[Ignore friction.]",
            "source_heading": "4-7 Newton's Laws and Vectors",
            "source_page": 123,
            "reviewed": True,
        }]
        self.assertEqual(bank.student_source_fidelity_issues(q, []), [])

    def test_verified_section_heading_is_not_copied_verbatim_as_editorial_prefix(self):
        q = self.question("[Ignore friction.] A rope lifts a box.",
                          "A rope lifts a box.")
        q["extraction"]["shared_source_instructions"] = [{
            "text": "[Ignore friction.]",
            "source_heading": "4-7 Newton's Laws and Vectors",
            "source_page": 123,
            "reviewed": True,
        }]
        problems = bank.student_source_fidelity_issues(q, [])
        self.assertTrue(any("copied verbatim" in e for e in problems), problems)

    def test_question_level_source_instruction_remains_allowed(self):
        q = self.question("Ignore friction. A rope lifts a box.",
                          "Ignore friction. A rope lifts a box.")
        self.assertEqual(bank.student_source_fidelity_issues(q, []), [])

    def test_unverified_shared_heading_does_not_allow_invented_assumptions(self):
        for note in (
            {"text": "[Ignore friction.]", "source_page": 123, "source_heading": "4-7 Newton's Laws and Vectors"},
            {"text": "[Ignore friction.]", "source_page": 123, "reviewed": True},
            {"text": "[Ignore friction.]", "source_heading": "4-7 Newton's Laws and Vectors", "reviewed": True},
        ):
            with self.subTest(note=note):
                q = self.question("[Ignore friction.] A rope lifts a box.", "A rope lifts a box.")
                q["extraction"]["shared_source_instructions"] = [note]
                self.assertTrue(any("unverified physical assumption" in e
                                    for e in bank.student_source_fidelity_issues(q, [])))

    def test_source_supported_ignore_air_resistance_is_allowed(self):
        q = self.question("Ignore air resistance. A stone falls.",
                          "Ignore air resistance. A stone falls.")
        self.assertEqual(bank.student_source_fidelity_issues(q, []), [])

    def test_source_mention_of_friction_does_not_authorize_neglect(self):
        q = self.question("Neglect friction. A block slides.", "The coefficient of friction is unknown.")
        self.assertTrue(any("unverified physical assumption" in e for e in
                            bank.student_source_fidelity_issues(q, [])))

    def test_clean_self_contained_stem_without_source_figure_is_allowed(self):
        q = self.question("A mower is pushed with a 45 degree force below the horizontal.",
                          "A mower is pushed with a 45 degree force below the horizontal.")
        self.assertEqual(bank.student_source_fidelity_issues(q, []), [])


if __name__ == "__main__":
    unittest.main()

