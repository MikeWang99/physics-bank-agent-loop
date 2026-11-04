"""Regression tests for the opt-in delivery extension; source loop remains untouched."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "skills/physics-bank-agent-loop/scripts/delivery.py"
spec = importlib.util.spec_from_file_location("delivery", DELIVERY)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class AnswerContractTests(unittest.TestCase):
    def setUp(self):
        self.question = {
            "id": "q001",
            "stem": "A force acts on a body. Which option is correct?",
            "choices": [{"label": "A", "text": "A"}, {"label": "B", "text": "B"}],
            "answer": {"label": "B", "text": None},
        }
        self.answer = {
            "id": "q001", "kind": "mcq", "correct_labels": ["B"],
            "detailed_explanation": "Use $F=ma$, not a guessed direction.",
            "creator": {"id": "writer"},
            "reviewer": {"id": "verifier", "independent": True, "verdict": "ACCEPT",
                         "notes": "Re-solved from original."},
        }

    def test_source_key_and_standard_answer_format(self):
        result = delivery.reviewed_answer(self.answer, self.question)
        self.assertEqual(result["label"], "B")
        self.assertTrue(result["text"].startswith("**Correct answer: B**"))
        self.assertIn("**Detailed explanation**", result["text"])
        self.assertEqual(result["origin"], "ai_enhanced")

    def test_source_key_conflict_never_auto_publishes(self):
        self.answer["correct_labels"] = ["A"]
        with self.assertRaisesRegex(ValueError, "conflicts"):
            delivery.reviewed_answer(self.answer, self.question)

    def test_same_agent_or_missing_verification_rejected(self):
        self.answer["reviewer"]["id"] = "writer"
        with self.assertRaisesRegex(ValueError, "must differ"):
            delivery.reviewed_answer(self.answer, self.question)
        self.answer["reviewer"]["id"] = "verifier"
        self.answer["reviewer"]["independent"] = False
        with self.assertRaisesRegex(ValueError, "not passed"):
            delivery.reviewed_answer(self.answer, self.question)

    def test_latex_boundary_validation(self):
        self.assertEqual(delivery.markdown_latex("$F=ma$", "value"), "$F=ma$")
        with self.assertRaisesRegex(ValueError, "unbalanced"):
            delivery.markdown_latex("$F=ma", "value")
        with self.assertRaisesRegex(ValueError, "backslash math delimiters"):
            delivery.markdown_latex(r"\(F=ma\)", "value")
        with self.assertRaisesRegex(ValueError, "mismatched"):
            delivery.markdown_latex("$F=ma$", "value")
        self.assertEqual(delivery.markdown_latex("$F=ma$", "value"), "$F=ma$")

    def test_frq_sections_are_separate(self):
        q = {"id": "q002", "stem": "Find the acceleration.", "answer": {}}
        response = {
            **self.answer, "id": "q002", "kind": "frq", "exam_answer": "$a=5\\,\\mathrm{m/s^2}$",
        }
        answer = delivery.reviewed_answer(response, q)
        self.assertIn("**Exam-style answer**", answer["text"])
        self.assertIn("**Detailed explanation**", answer["text"])
        self.assertEqual(answer["origin"], "ai_generated")
        self.assertIsNone(answer["label"])

    def test_topic_gate_rejects_missing_mapping_even_if_course_practice_publishes(self):
        item = {"version": {"metadata": {"physicsBank": {"classification": {"schema": "physics-question-classification/v1"}}, "practiceStep": {}}}}
        eligible, reason = delivery.topic_display_eligibility(item)
        self.assertFalse(eligible)
        self.assertIn("Topic Practice", reason)

    def test_hash_recomputes_after_answer_change(self):
        item = {
            "version": {"stem": "hello", "choices": [], "answer": {"solution": "old"},
                        "metadata": {}, "sourceYear": None, "sourceRef": None},
            "assets": [],
        }
        delivery.recalculate_hash(item)
        before = item["version"]["contentHash"]
        delivery.recalculate_hash(item)
        self.assertEqual(item["version"]["contentHash"], before)
        item["version"]["answer"]["solution"] = "new"
        delivery.recalculate_hash(item)
        self.assertNotEqual(before, item["version"]["contentHash"])


class MixedBatchTests(unittest.TestCase):
    def test_valid_question_prepares_while_unverified_question_goes_to_priority(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            bank = base / "bank"
            bank.mkdir()
            questions = [
                {"id": "q001", "stem": "Find the net force.", "choices": [
                    {"label": "A", "text": "Zero"}, {"label": "B", "text": "Non-zero"}],
                 "answer": {"label": "B"}, "asset_ids": []},
                {"id": "q002", "stem": "Needs human intervention.", "choices": [
                    {"label": "A", "text": "One"}, {"label": "B", "text": "Two"}],
                 "asset_ids": []},
            ]
            delivery.dump(bank / "questions.json", {"schema_version": "2.0", "questions": questions})
            delivery.dump(bank / "assets.json", {"schema_version": "2.0", "assets": []})
            delivery.dump(bank / "classification-taxonomy.json", {"course": "AP Physics 1"})
            config = base / "config.json"
            delivery.dump(config, {"schema": "pocket-cosmos-publish-config/v1",
                                   "practice_set": {"id": "test-bank", "system": "ap-physics-1",
                                                    "practice_kind": "mcq", "title": "Test Bank"}})
            answers = base / "answers.json"
            delivery.dump(answers, {"schema": delivery.ANSWERS_SCHEMA, "questions": [{
                "id": "q001", "kind": "mcq", "correct_labels": ["B"],
                "detailed_explanation": "Use $F=ma$ to decide.",
                "creator": {"id": "writer"},
                "reviewer": {"id": "verifier", "independent": True, "verdict": "ACCEPT",
                             "notes": "Independent calculation agreed with option B."},
            }]})
            report = delivery.run(bank, config, answers, base / "output", False)
            self.assertEqual(report["sourceQuestionCount"], 2)
            self.assertEqual(report["readyCount"], 1)
            self.assertEqual(report["highPriorityCount"], 2)
            self.assertFalse(report["published"])
            self.assertEqual({row["questionId"] for row in report["highPriorityReview"]}, {"q001", "q002"})
            self.assertEqual({row["status"] for row in report["highPriorityReview"]}, {"published_course_only", "not_published"})
            ready = delivery.load(base / "output/web-publish-ready.json")
            self.assertEqual(len(ready["questions"]), 1)
            compiled = ready["questions"][0]
            self.assertEqual(compiled["question"]["id"], "test-bank::q001")
            self.assertEqual(compiled["version"]["metadata"]["practiceStep"]["correctAnswer"], "B")
            self.assertEqual(compiled["version"]["metadata"]["physicsBank"]["deliveryAnswer"]["origin"], "ai_enhanced")


if __name__ == "__main__":
    unittest.main()
