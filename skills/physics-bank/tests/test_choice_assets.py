#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

ORG = load("organize_choice_assets", "organize_choice_assets.py")
VAL = load("validate_bank", "validate_bank.py")


def base_question():
    return {
        "id": "fma-2016-q005", "stem": "Choose the graph.", "source_pages": [1],
        "content_format": "markdown+latex", "answer": {"text": None, "label": "A", "evidence": "official"},
        "choices": [{"label": "A", "text": ""}, {"label": "B", "text": ""}],
        "requires_manual_review": False, "extraction": {"text_reviewed": True}, "asset_ids": ["a1"],
    }


class ChoiceAssetTests(unittest.TestCase):
    def test_organizer_moves_choice_to_canonical_folder_and_binds_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "assets" / "figures").mkdir(parents=True)
            src = root / "assets" / "figures" / "raw.png"; src.write_bytes(b"png")
            qpath = root / "questions.json"; apath = root / "assets.json"
            qpath.write_text(json.dumps({"questions": [base_question()]}))
            apath.write_text(json.dumps({"assets": [{
                "id": "a1", "file": "assets/figures/raw.png", "role": "choice", "choice_label": "A",
                "owners": ["fma-2016-q005"], "reviewed": True, "crop": {"isolated_choice": True, "reviewed": True}
            }]}))
            report = ORG.organize(qpath, apath, apply=True)
            self.assertEqual(report["status"], "ok", report)
            q = json.loads(qpath.read_text())["questions"][0]
            a = json.loads(apath.read_text())["assets"][0]
            self.assertEqual(q["choices"][0]["asset_ids"], ["a1"])
            self.assertEqual(a["file"], "assets/choices/fma-2016-q005/A-01.png")
            self.assertTrue((root / a["file"]).exists())
            self.assertFalse(src.exists())

    def test_organizer_refuses_unreviewed_or_nonisolated_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "x.png").write_bytes(b"x")
            qpath = root / "questions.json"; apath = root / "assets.json"
            qpath.write_text(json.dumps({"questions": [base_question()]}))
            apath.write_text(json.dumps({"assets": [{
                "id": "a1", "file": "x.png", "role": "choice", "choice_label": "A", "owners": ["fma-2016-q005"],
                "reviewed": True, "crop": {"isolated_choice": False}
            }]}))
            report = ORG.organize(qpath, apath, apply=False)
            self.assertEqual(report["status"], "error")
            self.assertTrue(any("isolated_choice" in e for e in report["errors"]))

    def test_validator_accepts_canonical_choice_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root / "assets" / "choices" / "fma-2016-q005"; p.mkdir(parents=True)
            Image.new("RGB", (40, 30), "white").save(p / "A-01.png")
            review_hash = hashlib.sha256((p / "A-01.png").read_bytes()).hexdigest()
            q = base_question(); q["choices"][0]["asset_ids"] = ["a1"]
            qpath = root / "questions.json"; apath = root / "assets.json"
            qpath.write_text(json.dumps({"questions": [q]}))
            apath.write_text(json.dumps({"assets": [{
                "id": "a1", "file": "assets/choices/fma-2016-q005/A-01.png", "role": "choice", "choice_label": "A",
                "choice_index": 1, "owners": ["fma-2016-q005"], "reviewed": True,
                "crop": {"isolated_choice": True, "reviewed": True, "review_sha256": review_hash}
            }]}))
            report = VAL.validate(qpath, apath, True, True)
            self.assertEqual(report["status"], "ok", report)

    def test_validator_rejects_combined_or_wrong_folder_choice_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "combined.png").write_bytes(b"x")
            q = base_question(); q["choices"][0]["asset_ids"] = ["a1"]
            qpath = root / "questions.json"; apath = root / "assets.json"
            qpath.write_text(json.dumps({"questions": [q]}))
            apath.write_text(json.dumps({"assets": [{
                "id": "a1", "file": "combined.png", "role": "choice", "choice_label": "A", "choice_index": 1,
                "owners": ["fma-2016-q005"], "reviewed": True, "crop": {"isolated_choice": False}
            }]}))
            report = VAL.validate(qpath, apath, True, True)
            self.assertEqual(report["status"], "error")
            self.assertTrue(any("isolated_choice" in e for e in report["errors"]))
            self.assertTrue(any("assets/choices" in e for e in report["errors"]))

    def test_multiple_images_for_one_choice_require_explicit_unique_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "a.png").write_bytes(b"a"); (root / "b.png").write_bytes(b"b")
            qpath = root / "questions.json"; apath = root / "assets.json"
            qpath.write_text(json.dumps({"questions": [base_question()]}))
            apath.write_text(json.dumps({"assets": [
                {"id":"a1","file":"a.png","role":"choice","choice_label":"A","owners":["fma-2016-q005"],"reviewed":True,"crop":{"isolated_choice":True}},
                {"id":"a2","file":"b.png","role":"choice","choice_label":"A","owners":["fma-2016-q005"],"reviewed":True,"crop":{"isolated_choice":True}},
            ]}))
            report = ORG.organize(qpath, apath, apply=False)
            self.assertEqual(report["status"], "error")
            self.assertTrue(any("choice_index" in e for e in report["errors"]))


if __name__ == "__main__": unittest.main()
