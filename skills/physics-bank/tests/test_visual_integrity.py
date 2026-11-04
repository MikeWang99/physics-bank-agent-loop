#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


DISC = load("discover_pdf_assets", "discover_pdf_assets.py")
VAL = load("validate_bank_visual", "validate_bank.py")
CROP = load("crop_figure_visual", "crop_figure.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_source_pdf(path: Path, with_label: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(230, 230, 380, 300), width=1.2)
    if with_label:
        page.insert_text((178, 260), "12 V", fontsize=12)
    doc.save(path)


def write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (120, 80), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 100, 60], outline="black", width=2)
    img.save(path)


def make_bank(root: Path, *, with_label: bool):
    source_pdf = root / "assets" / "source" / "paper.pdf"
    asset_png = root / "assets" / "figures" / "fig.png"
    write_source_pdf(source_pdf, with_label=with_label)
    write_png(asset_png)
    bbox = [215.0, 215.0, 400.0, 315.0]
    q = {
        "id": "q1",
        "context": "",
        "stem": "Use the circuit shown.",
        "source_pages": [1],
        "content_format": "markdown+latex",
        "answer": {"text": None, "label": None, "evidence": "not-provided"},
        "requires_manual_review": False,
        "review_reasons": [],
        "extraction": {"text_reviewed": True},
        "asset_ids": ["fig1"],
        "layout_blocks": [
            {"type": "figure", "asset_id": "fig1", "source_anchor": {"relation": "question_start"}},
            {"type": "text", "text": "Use the circuit shown."},
        ],
        "layout_review": {"reviewed": True, "method": "source-page-visual"},
    }
    asset = {
        "id": "fig1",
        "file": "assets/figures/fig.png",
        "role": "stem",
        "owners": ["q1"],
        "reviewed": True,
        "source": {"file": "assets/source/paper.pdf", "page": 1, "bbox": bbox},
        "crop": {
            "reviewed": True,
            "review_sha256": sha(asset_png),
            "review_source_sha256": sha(source_pdf),
            "reviewed_source_bbox": bbox,
            "source_neighborhood_reviewed": True,
            "review_method": "test",
        },
    }
    qpath = root / "questions.json"
    apath = root / "assets.json"
    qpath.write_text(json.dumps({"questions": [q]}), encoding="utf-8")
    apath.write_text(json.dumps({"assets": [asset]}), encoding="utf-8")
    return qpath, apath, asset_png


class VisualIntegrityTests(unittest.TestCase):
    def test_discovery_absorbs_nearby_short_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "paper.pdf"
            write_source_pdf(pdf, with_label=True)
            doc = fitz.open(pdf)
            page = doc[0]
            rects, _ = DISC.graphics_on_page(page)
            groups = DISC.clusters(rects)
            self.assertTrue(groups)
            lines = DISC.text_lines(page)
            labels = DISC.nearby_short_labels(groups[0], lines, max_gap=42)
            self.assertTrue(any(item["text"] == "12 V" for item in labels), labels)
            expanded = DISC.expand_with_labels(groups[0], labels)
            label_box = next(fitz.Rect(item["bbox"]) for item in labels if item["text"] == "12 V")
            self.assertLessEqual(expanded.x0, label_box.x0)

    def test_validator_rejects_label_just_outside_source_bbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qpath, apath, _ = make_bank(root, with_label=True)
            report = VAL.validate(qpath, apath, strict=True, require_text_review=True)
            self.assertEqual(report["status"], "error")
            self.assertTrue(
                any("possible omitted diagram label" in e and "12 V" in e for e in report["errors"]),
                report["errors"],
            )

    def test_validator_rejects_asset_changed_after_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qpath, apath, asset_png = make_bank(root, with_label=False)
            img = Image.open(asset_png).convert("RGB")
            draw = ImageDraw.Draw(img)
            draw.line([30, 30, 90, 50], fill="black", width=2)
            img.save(asset_png)
            report = VAL.validate(qpath, apath, strict=True, require_text_review=True)
            self.assertTrue(
                any("changed after visual review" in e for e in report["errors"]),
                report["errors"],
            )

    def test_destructive_crop_invalidates_review_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "assets" / "figures" / "fig.png"
            write_png(image)
            apath = root / "assets.json"
            apath.write_text(json.dumps({
                "assets": [{
                    "id": "fig1",
                    "file": "assets/figures/fig.png",
                    "role": "stem",
                    "owners": ["q1"],
                    "reviewed": True,
                    "crop": {
                        "reviewed": True,
                        "review_sha256": sha(image),
                        "review_source_sha256": "a" * 64,
                        "reviewed_source_bbox": [1, 1, 2, 2],
                        "source_neighborhood_reviewed": True,
                        "review_method": "test",
                    },
                }]
            }), encoding="utf-8")
            rc = CROP.cmd_box(image, (5, 5, 115, 75))
            self.assertEqual(rc, 0)
            asset = json.loads(apath.read_text(encoding="utf-8"))["assets"][0]
            self.assertFalse(asset["reviewed"])
            self.assertFalse(asset["crop"]["reviewed"])
            self.assertNotIn("review_sha256", asset["crop"])
            self.assertNotIn("source_neighborhood_reviewed", asset["crop"])


if __name__ == "__main__":
    unittest.main()
