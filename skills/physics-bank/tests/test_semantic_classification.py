#!/usr/bin/env python3
import importlib.util
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from difficulty_fixtures import rating

ROOT = Path(__file__).parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


DERIVE = load("derive_semantic_tags", "derive_semantic_tags.py")
VALIDATE = load("validate_semantic_classification", "validate_semantic_classification.py")
REFERENCE = json.loads((ROOT / "references" / "semantic-taxonomy.json").read_text(encoding="utf-8"))


def taxonomy():
    return {
        "schema": "physics-bank-curriculum-taxonomy/v1",
        "course": {"id": "fma", "name": "F=ma", "basis": "competition-bank-taxonomy"},
        "units": [{
            "id": "dynamics",
            "name": "Dynamics",
            "topics": [{
                "id": "newtons-laws",
                "name": "Newton's Laws",
                "subtopics": [
                    {"id": "friction", "name": "Friction"},
                    {"id": "connected-bodies", "name": "Connected bodies"},
                ],
            }],
        }],
    }


def question():
    return {
        "id": "fma-2024-q001",
        "year": 2024,
        "tags": ["year:2024", "custom:keep-me", "topic:stale-topic"],
        "classification": {
            "schema": "physics-question-classification/v1",
            "status": "reviewed",
            "curriculum": {
                "course_id": "fma",
                "unit_id": "dynamics",
                "topic_id": "newtons-laws",
                "subtopic_ids": ["friction"],
            },
            "physics_domain": "mechanics",
            "primary_topic": {
                "name": "Newton's second law",
                "evidence": "The unknown is determined from the net-force equation.",
            },
            "secondary_topics": [{
                "name": "Friction",
                "evidence": "Friction contributes one force but does not organize the whole solution.",
            }],
            "knowledge_points": [{
                "name": "Static friction adjusts up to a limiting value",
                "role": "required",
                "evidence": "The friction force cannot be assumed to equal its maximum value without the limiting condition.",
            }],
            "solution_models": [{
                "name": "Newton's second law",
                "kind": "governing_law",
                "role": "primary",
                "evidence": "The net-force relation bridges the identified forces to the acceleration.",
            }],
            "skills": [
                {
                    "id": "model_selection",
                    "evidence": "The student must select the correct force model before calculating.",
                },
                {
                    "id": "free_body_diagram",
                    "evidence": "The relevant forces must be identified before the governing equation is written.",
                },
            ],
            "difficulty": rating(),
            "confidence": 0.92,
            "review": {"reviewed": True, "method": "model-semantic-analysis"},
        },
    }


def derived_data():
    data = {"questions": [question()]}
    return DERIVE.derive(data, taxonomy())


class SemanticClassificationTests(unittest.TestCase):
    def test_valid_classification_and_derived_fields_pass(self):
        data = derived_data()
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertEqual(report["status"], "ok", report["errors"])
        q = data["questions"][0]
        self.assertEqual(q["course"], "F=ma")
        self.assertEqual(q["unit"], "Dynamics")
        self.assertEqual(q["topic"], "Newton's Laws")
        self.assertEqual(q["subtopics"], ["Friction"])
        self.assertIn("course:fma", q["tags"])
        self.assertIn("unit:dynamics", q["tags"])
        self.assertIn("topic:newtons-laws", q["tags"])
        self.assertIn("subtopic:friction", q["tags"])
        self.assertIn("skill:model-selection", q["tags"])
        self.assertIn("difficulty:3", q["tags"])
        self.assertIn("year:2024", q["tags"])
        self.assertIn("custom:keep-me", q["tags"])
        self.assertNotIn("topic:stale-topic", q["tags"])

    def test_unknown_topic_is_rejected(self):
        data = derived_data()
        data["questions"][0]["classification"]["curriculum"]["topic_id"] = "energy"
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertTrue(any("unknown curriculum topic_id" in e for e in report["errors"]))

    def test_missing_evidence_is_rejected(self):
        data = derived_data()
        data["questions"][0]["classification"]["primary_topic"]["evidence"] = ""
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertTrue(any("primary_topic requires name + evidence" in e for e in report["errors"]))

    def test_low_confidence_requires_review(self):
        data = derived_data()
        data["questions"][0]["classification"]["confidence"] = 0.6
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertTrue(any("below review threshold" in e for e in report["errors"]))

    def test_primary_solution_model_is_required(self):
        data = derived_data()
        data["questions"][0]["classification"]["solution_models"][0]["role"] = "secondary"
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertTrue(any("at least one solution_model" in e for e in report["errors"]))

    def test_skill_must_use_controlled_vocabulary(self):
        data = derived_data()
        data["questions"][0]["classification"]["skills"][0]["id"] = "smart_thinking"
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertTrue(any("is not controlled vocabulary" in e for e in report["errors"]))

    def test_stale_derived_field_is_rejected(self):
        data = derived_data()
        data["questions"][0]["topic"] = "Energy"
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertTrue(any("derived field topic is stale" in e for e in report["errors"]))

    def test_stale_generated_tag_is_rejected(self):
        data = derived_data()
        data["questions"][0]["tags"].append("topic:energy")
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertTrue(any("stale/unexpected derived semantic tag" in e for e in report["errors"]))

    def test_duplicate_subtopic_mapping_is_rejected(self):
        data = derived_data()
        data["questions"][0]["classification"]["curriculum"]["subtopic_ids"] = ["friction", "friction"]
        DERIVE.derive(data, taxonomy())
        report = VALIDATE.validate(data, taxonomy(), REFERENCE, strict=True)
        self.assertTrue(any("duplicate curriculum subtopic_ids" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
