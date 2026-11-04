"""Difficulty publication gates: levels, evidence, review state and migration."""
import unittest
from copy import deepcopy
from test_semantic_classification import DERIVE, VALIDATE, REFERENCE, question, taxonomy


from difficulty_fixtures import rating


def data_for(difficulty):
    q = question()
    q["answer"] = {"label": None, "text": None, "evidence": "not-provided"}
    q["classification"]["difficulty"] = deepcopy(difficulty)
    return DERIVE.derive({"questions": [q]}, taxonomy())


class TimbadDifficultyTests(unittest.TestCase):
    def report(self, d, strict=True):
        return VALIDATE.validate(data_for(d), taxonomy(), REFERENCE, strict=strict)

    def test_all_seven_approved_levels_can_publish(self):
        for level in range(1, 8):
            d = rating(level)
            if level >= 5:
                d.update(key_insights=["An independently discovered change of model supplies the missing constraint."], insight_depth="DEEP")
            with self.subTest(level=level):
                self.assertEqual(self.report(d)["errors"], [])

    def test_legacy_five_level_rating_requires_reassessment_for_publication(self):
        d = {"level": 3, "drivers": ["standard multistep"]}
        self.assertTrue(self.report(d)["errors"])
        self.assertEqual(self.report(d, strict=False)["errors"], [])

    def test_review_states_store_without_becoming_publishable(self):
        for status, level in [("REJECTED", 0), ("NEEDS_REVIEW", None), ("REVISE", 3)]:
            d = rating()
            d.update(review_status=status, level=level, overall_level=f"L{level}" if level is not None else None,
                     review_notes="Missing source diagram or confirmed issue.", needs_human_review=True)
            if status == "REJECTED":
                d.update(rejection_reason="FATAL_PHYSICS_ERROR", question_quality_flags=["FATAL_PHYSICS_ERROR"])
            if status in {"REJECTED", "NEEDS_REVIEW"}:
                d["timbad"] = {k: {"score": None, "rationale": "Cannot assess.", "evidence": "Source issue."} for k in "TIMBAD"}
                d["final_answer"] = None
            with self.subTest(status=status):
                self.assertEqual(self.report(d, strict=False)["errors"], [])
                self.assertTrue(self.report(d)["errors"])
                q = data_for(d)["questions"][0]
                self.assertFalse(any(t.startswith("difficulty:") for t in q["tags"]))

    def test_level_and_status_must_agree(self):
        for status, level in [("APPROVED", 0), ("NEEDS_REVIEW", 3), ("REJECTED", 2), ("REVISE", 0)]:
            d = rating(level)
            d["review_status"] = status
            with self.subTest(status=status):
                self.assertTrue(self.report(d, strict=False)["errors"])

    def test_overall_label_matches_numeric_mirror(self):
        d = rating()
        d["overall_level"] = "L6"
        self.assertTrue(self.report(d)["errors"])

    def test_unknown_rubric_or_version_is_rejected(self):
        for field in ["rubric_id", "rubric_version"]:
            d = rating()
            d[field] = "unknown"
            self.assertTrue(self.report(d)["errors"])

    def test_dimension_scores_reject_bool_strings_fractions_and_out_of_range(self):
        for score in [True, "2", 1.5, -1, 3, None]:
            d = rating()
            d["timbad"]["T"]["score"] = score
            with self.subTest(score=score):
                self.assertTrue(self.report(d)["errors"])

    def test_exactly_six_dimensions_and_concrete_evidence_required(self):
        for change in ["missing", "extra", "rationale", "evidence"]:
            d = rating()
            if change == "missing": del d["timbad"]["D"]
            elif change == "extra": d["timbad"]["X"] = d["timbad"]["D"]
            else: d["timbad"]["D"][change] = ""
            with self.subTest(change=change):
                self.assertTrue(self.report(d)["errors"])

    def test_bottlenecks_must_be_controlled_and_distinct(self):
        for primary, secondary in [("M", "M"), ("X", "NONE")]:
            d = rating()
            d.update(primary_bottleneck=primary, secondary_bottleneck=secondary)
            self.assertTrue(self.report(d)["errors"])

    def test_complete_audit_is_required_for_approved_rating(self):
        for field in ["overall_reason", "boundary_reason", "solution_outline", "final_answer", "math_tools", "prerequisites", "key_skills", "topic", "subtopic"]:
            d = rating()
            del d[field]
            with self.subTest(field=field):
                self.assertTrue(self.report(d)["errors"])

    def test_high_levels_need_key_insight_and_depth(self):
        for level in [5, 6, 7]:
            self.assertTrue(self.report(rating(level))["errors"])

    def test_low_confidence_or_pending_human_review_cannot_publish(self):
        for update in [{"rating_confidence": "LOW"}, {"needs_human_review": True}]:
            d = rating()
            d.update(update)
            self.assertTrue(self.report(d)["errors"])

    def test_derive_preserves_audit_and_does_not_overwrite_source_answer(self):
        data = data_for(rating())
        q = data["questions"][0]
        self.assertEqual(q["difficulty"], 3)
        self.assertIn("difficulty:3", q["tags"])
        self.assertEqual(q["classification"]["difficulty"], rating())
        self.assertEqual(q["answer"], {"label": None, "text": None, "evidence": "not-provided"})

    def test_pending_review_ratings_are_not_usable_search_tiers(self):
        for update in [{"needs_human_review": True}, {"rating_confidence": "LOW", "needs_human_review": True}]:
            d = rating()
            d.update(update)
            q = data_for(d)["questions"][0]
            self.assertIsNone(q["difficulty"])
            self.assertFalse(any(t.startswith("difficulty:") for t in q["tags"]))

    def test_malformed_enum_values_return_errors_without_crashing(self):
        for field in ["review_status", "primary_bottleneck", "secondary_bottleneck", "insight_depth", "rating_confidence"]:
            d = rating()
            d[field] = {"invalid": True}
            with self.subTest(field=field):
                self.assertTrue(self.report(d)["errors"])

    def test_unrated_record_still_requires_explicit_numeric_level_key(self):
        d = rating()
        d.update(review_status="NEEDS_REVIEW", overall_level=None, needs_human_review=True, review_notes="Missing graph.")
        del d["level"]
        self.assertTrue(self.report(d, strict=False)["errors"])

    def test_missing_material_can_leave_unknown_audit_arrays_empty(self):
        d = rating()
        d.update(review_status="NEEDS_REVIEW", level=None, overall_level=None,
                 review_notes="Missing critical source diagram.", needs_human_review=True,
                 drivers=[], solution_outline=[], final_answer=None)
        d["timbad"] = {k: {"score": None, "rationale": "", "evidence": ""} for k in "TIMBAD"}
        self.assertEqual(self.report(d, strict=False)["errors"], [])


if __name__ == "__main__":
    unittest.main()
