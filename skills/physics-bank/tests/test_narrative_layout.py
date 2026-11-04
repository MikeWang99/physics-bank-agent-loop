#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("validate_bank", ROOT / "scripts" / "validate_bank.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def base_question():
    return {
        "id": "q46",
        "context": "",
        "stem": "A student draws a correct bar chart. A sample of the gas is taken from the state.",
        "source_pages": [1],
        "content_format": "markdown+latex",
        "answer": {"text": None, "label": None, "evidence": "not-provided"},
        "requires_manual_review": False,
        "review_reasons": [],
        "extraction": {"text_reviewed": True},
        "asset_ids": ["fig-main", "fig-bar"],
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assets(root: Path):
    figures = root / "assets" / "figures"
    source = root / "assets" / "source"
    figures.mkdir(parents=True, exist_ok=True)
    source.mkdir(parents=True, exist_ok=True)

    Image.new("RGB", (80, 60), "white").save(figures / "main.png")
    Image.new("RGB", (80, 60), "white").save(figures / "bar.png")

    source_pdf = source / "paper.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(source_pdf)
    source_hash = _sha(source_pdf)

    def entry(asset_id, filename, bbox):
        return {
            "id": asset_id,
            "file": f"assets/figures/{filename}",
            "role": "stem",
            "owners": ["q46"],
            "reviewed": True,
            "source": {"file": "assets/source/paper.pdf", "page": 1, "bbox": bbox},
            "crop": {
                "reviewed": True,
                "review_sha256": _sha(figures / filename),
                "review_source_sha256": source_hash,
                "reviewed_source_bbox": bbox,
                "source_neighborhood_reviewed": True,
                "review_method": "test",
            },
        }

    return {
        "assets": [
            entry("fig-main", "main.png", [50, 80, 400, 210]),
            entry("fig-bar", "bar.png", [70, 240, 390, 330]),
        ]
    }


def valid_layout():
    return [
        {"type": "figure", "asset_id": "fig-main", "source_anchor": {"relation": "question_start"}},
        {
            "type": "figure",
            "asset_id": "fig-bar",
            "source_anchor": {"relation": "before", "text": "A student draws a correct bar chart"},
        },
        {"type": "text", "text": "A student draws a correct bar chart. A sample of the gas is taken from the state."},
    ]


class NarrativeLayoutTests(unittest.TestCase):
    def run_validation(self, question, asset_data):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Recreate asset files inside this temp root.
            asset_data = assets(root)
            (root / "questions.json").write_text(json.dumps({"questions": [question]}), encoding="utf-8")
            (root / "assets.json").write_text(json.dumps(asset_data), encoding="utf-8")
            return MOD.validate(root / "questions.json", root / "assets.json", strict=True, require_text_review=True)

    def test_valid_reviewed_layout_passes(self):
        q = base_question()
        q["layout_blocks"] = valid_layout()
        q["layout_review"] = {"reviewed": True, "method": "source-page-visual", "reviewed_against_pages": [1]}
        report = self.run_validation(q, None)
        self.assertEqual(report["status"], "ok", report["errors"])

    def test_stem_assets_require_layout_blocks(self):
        q = base_question()
        report = self.run_validation(q, None)
        self.assertTrue(any("require explicit layout_blocks" in e for e in report["errors"]))

    def test_layout_requires_all_figures_exactly_once(self):
        q = base_question()
        q["layout_blocks"] = [
            {"type": "figure", "asset_id": "fig-main", "source_anchor": {"relation": "question_start"}},
            {"type": "text", "text": q["stem"]},
        ]
        q["layout_review"] = {"reviewed": True, "method": "source-page-visual"}
        report = self.run_validation(q, None)
        self.assertTrue(any("layout figure coverage mismatch" in e for e in report["errors"]))

    def test_layout_text_cannot_drop_source_prose(self):
        q = base_question()
        q["layout_blocks"] = [
            {"type": "figure", "asset_id": "fig-main", "source_anchor": {"relation": "question_start"}},
            {"type": "figure", "asset_id": "fig-bar", "source_anchor": {"relation": "question_end"}},
            {"type": "text", "text": "A student draws a correct bar chart."},
        ]
        q["layout_review"] = {"reviewed": True, "method": "source-page-visual"}
        report = self.run_validation(q, None)
        self.assertTrue(any("preserve the complete context + stem" in e for e in report["errors"]))

    def test_anchor_phrase_must_exist_in_narrative(self):
        q = base_question()
        q["layout_blocks"] = valid_layout()
        q["layout_blocks"][1]["source_anchor"]["text"] = "phrase that is not in the question"
        q["layout_review"] = {"reviewed": True, "method": "source-page-visual"}
        report = self.run_validation(q, None)
        self.assertTrue(any("source_anchor text not found" in e for e in report["errors"]))

    def test_stem_asset_requires_source_bbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = assets(root)
            del a["assets"][0]["source"]["bbox"]
            q = base_question()
            q["layout_blocks"] = valid_layout()
            q["layout_review"] = {"reviewed": True, "method": "source-page-visual"}
            (root / "questions.json").write_text(json.dumps({"questions": [q]}), encoding="utf-8")
            (root / "assets.json").write_text(json.dumps(a), encoding="utf-8")
            report = MOD.validate(root / "questions.json", root / "assets.json", strict=True, require_text_review=True)
            self.assertTrue(any("source.bbox" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
