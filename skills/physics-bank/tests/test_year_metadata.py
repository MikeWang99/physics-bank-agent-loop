#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


STAMP = load("stamp_exam_year", "stamp_exam_year.py")
VALIDATE = load("validate_year_metadata", "validate_year_metadata.py")


class YearMetadataTests(unittest.TestCase):
    def test_four_digit_year_is_stamped(self):
        data = {"questions": [{"id": "q1", "source": {"file": "2016_Fma_exam.pdf"}}]}
        result = STAMP.stamp(data)
        q = result["questions"][0]
        self.assertEqual(q["year"], 2016)
        self.assertEqual(q["source"]["year"], 2016)
        self.assertIn("year:2016", q["tags"])
        self.assertEqual(VALIDATE.validate(result)["status"], "ok")

    def test_two_digit_exam_filename_maps_16_to_2016(self):
        data = {"questions": [{"id": "q1", "source": {"file": "Fma_16_exam.pdf"}}]}
        result = STAMP.stamp(data)
        self.assertEqual(result["questions"][0]["year"], 2016)
        self.assertEqual(result["questions"][0]["year_evidence"]["method"], "source-two-digit")

    def test_explicit_year_overrides_opaque_filename(self):
        data = {"questions": [{"id": "q1", "source": {"file": "paper_final.pdf"}}]}
        result = STAMP.stamp(data, explicit_year=2018)
        self.assertEqual(result["questions"][0]["year"], 2018)
        self.assertEqual(result["questions"][0]["year_evidence"]["method"], "explicit")

    def test_missing_year_enters_manual_review(self):
        data = {"questions": [{"id": "q1", "source": {"file": "paper_final.pdf"}}]}
        result = STAMP.stamp(data)
        q = result["questions"][0]
        self.assertIsNone(q["year"])
        self.assertTrue(q["requires_manual_review"])
        self.assertIn("missing_exam_year", q["review_reasons"])
        self.assertEqual(VALIDATE.validate(result)["status"], "error")

    def test_ambiguous_year_is_not_guessed(self):
        data = {"questions": [{"id": "q1", "source": {"file": "Fma_16_17_exam.pdf"}}]}
        result = STAMP.stamp(data)
        q = result["questions"][0]
        self.assertIsNone(q["year"])
        self.assertIn("ambiguous_exam_year", q["review_reasons"])

    def test_existing_non_year_tags_are_preserved(self):
        data = {"questions": [{"id": "q1", "source": {"file": "2020_BPhO_paper.pdf"}, "tags": ["mechanics", "year:2019"]}]}
        result = STAMP.stamp(data)
        tags = result["questions"][0]["tags"]
        self.assertIn("mechanics", tags)
        self.assertIn("year:2020", tags)
        self.assertNotIn("year:2019", tags)


if __name__ == "__main__":
    unittest.main()
