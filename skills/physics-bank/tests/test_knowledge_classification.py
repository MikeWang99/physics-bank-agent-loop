"""Unified UID integrity + independent review, preserving v1 TIMBAD."""
from __future__ import annotations
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from difficulty_fixtures import rating

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT))
import knowledge_taxonomy as KT
import validate_knowledge_classification as VC
import derive_semantic_tags as DERIVE
import validate_year_metadata as YEARS

UID = "dbe04cf4-bae5-5e45-9b21-d8e2cb54f100"

def taxonomy_file(path):
    value = {"metadata": {"version": "test-v1", "counts": {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0}},
             "taxonomy": [{"id": "03", "uid": UID, "name_en": "Mechanics",
                           "name_zh": "力学", "level": 1, "parent_id": None,
                           "order": 1, "children": []}]}
    path.write_text(json.dumps(value), encoding="utf-8")
    return KT.load_knowledge_taxonomy(path, verify_lock=False)

def question(tax):
    return {
      "id": "fma-existing-id", "source_system": "competition", "source_event": "fma",
      "stem": "A body moves along a circular track. Find the force.", "tags": ["custom:high-value", "year:2019", "topic:stale"],
      "classification": {
        "schema": "physics-question-classification/v2", "status": "reviewed",
        "primary_knowledge_uid": UID, "confidence": 0.8,
        "taxonomy": {"version": tax["version"], "sha256": tax["sha256"]},
        "physics_analysis": {"required_concepts": ["radial dynamics"], "solution_summary": "Resolve the forces.",
                             "latest_required_reason": "Only force analysis is required."},
        "candidates": [{"uid": UID, "decision": "selected", "reason": "Covers the solution."}],
        "review": {"reviewed": True, "method": "independent-physics-check",
                   "initial_uid": UID, "independent_uid": UID,
                   "agreement": True, "cross_chapter_checked": True},
        "difficulty": rating(),
      }
    }

class KnowledgeClassificationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.tax = taxonomy_file(Path(self.folder.name) / "taxonomy.json")
        self.q = question(self.tax)
        DERIVE.derive_question(self.q, {})
    def tearDown(self):
        self.folder.cleanup()
    def test_exact_uid_approved_without_year(self):
        self.assertEqual(VC.validate_question(self.q, self.tax, True), [])
        self.assertEqual(YEARS.validate({"questions": [self.q]})["errors"], [])
        self.assertEqual(self.q["difficulty"], 3)
        self.assertEqual(self.q["tags"], ["custom:high-value", "year:2019", "difficulty:3"])
        self.assertNotIn("topic", self.q)
    def test_all_timbad_levels_up_to_l7(self):
        for level in range(1,8):
            q = copy.deepcopy(self.q)
            q["classification"]["difficulty"] = rating(level)
            if level >= 5:
                q["classification"]["difficulty"].update(key_insights=["Critical physics insight."], insight_depth="DEEP")
            DERIVE.derive_question(q,{})
            self.assertEqual(VC.validate_question(q,self.tax,True), [],level)
    def test_unknown_uid_and_forged_version_block(self):
        q=copy.deepcopy(self.q)
        q["classification"]["primary_knowledge_uid"]="00000000-0000-0000-0000-000000000000"
        self.assertTrue(VC.validate_question(q,self.tax,True))
        q=copy.deepcopy(self.q)
        q["classification"]["taxonomy"]["sha256"]="0"*64
        self.assertTrue(VC.validate_question(q,self.tax,True))
    def test_conflicting_independent_review_blocks(self):
        q=copy.deepcopy(self.q);q["classification"]["review"]["agreement"]=False
        self.assertTrue(any("independent review" in e for e in VC.validate_question(q,self.tax,True)))
    def test_incomplete_analysis_blocks_publish(self):
        q=copy.deepcopy(self.q);q["classification"]["physics_analysis"]["solution_summary"]=""
        self.assertTrue(VC.validate_question(q,self.tax,True))
    def test_missing_source_event_for_generic_contest(self):
        q=copy.deepcopy(self.q);q.pop("source_event")
        self.assertTrue(any("source_event" in e for e in VC.validate_question(q,self.tax,True)))
    def test_review_pending_can_hold_null_uid_but_not_publish(self):
        q=copy.deepcopy(self.q)
        q["classification"]["primary_knowledge_uid"]=None
        q["classification"]["status"]="needs_review"
        q["classification"]["difficulty"]["review_status"]="NEEDS_REVIEW"
        q["classification"]["difficulty"]["level"]=None
        q["classification"]["difficulty"]["overall_level"]=None
        q["classification"]["difficulty"]["needs_human_review"]=True
        q["classification"]["difficulty"]["review_notes"]="Missing original figure."
        for item in q["classification"]["difficulty"]["timbad"].values():
            item["score"]=None
        q["difficulty"]=None
        self.assertEqual(VC.validate_question(q,self.tax,False), [])
        self.assertTrue(VC.validate_question(q,self.tax,True))
    def test_known_year_does_not_require_redundant_tag_in_v2(self):
        q=copy.deepcopy(self.q);q["year"]=2024;q["source"]={"year":2024}
        q["tags"]=["custom:high-value"]
        self.assertEqual(YEARS.validate({"questions":[q]})["errors"],[])
    def test_does_not_change_question_identity_or_timbad(self):
        original=copy.deepcopy(self.q["classification"]["difficulty"])
        DERIVE.derive_question(self.q,{})
        self.assertEqual(self.q["id"],"fma-existing-id")
        self.assertEqual(self.q["classification"]["difficulty"], original)

if __name__=="__main__":
    unittest.main()
