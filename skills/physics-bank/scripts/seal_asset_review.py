#!/usr/bin/env python3
"""Seal visual review metadata for final question-bank assets.

A plain reviewed=true boolean can become stale after the PNG or source bbox is
changed. This command records content hashes and the exact reviewed source bbox.
Strict validation later rejects any asset whose file, source PDF, or bbox no
longer matches the reviewed state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _valid_bbox(value) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        x0, y0, x1, y1 = (float(v) for v in value)
    except (TypeError, ValueError):
        return False
    return x1 > x0 and y1 > y0


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _text_lines(page: fitz.Page) -> list[dict]:
    out = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if not text:
                continue
            box = fitz.Rect(line.get("bbox", (0, 0, 0, 0)))
            if not box.is_empty:
                out.append({"text": " ".join(text.split()), "bbox": box})
    return out


def nearby_text_risks(page: fitz.Page, rect: fitz.Rect, gap: float = 42.0) -> list[dict]:
    risks = []
    for item in _text_lines(page):
        text = item["text"]
        box = item["bbox"]
        if len(text) > 24 or box.height > 32:
            continue

        if rect.intersects(box):
            if not rect.contains(box):
                risks.append({"kind": "crosses_bbox", "text": text})
            continue

        v_overlap = _overlap(rect.y0, rect.y1, box.y0, box.y1)
        h_overlap = _overlap(rect.x0, rect.x1, box.x0, box.x1)
        side_gap = min(
            rect.x0 - box.x1 if box.x1 <= rect.x0 else float("inf"),
            box.x0 - rect.x1 if box.x0 >= rect.x1 else float("inf"),
        )
        vertical_gap = min(
            rect.y0 - box.y1 if box.y1 <= rect.y0 else float("inf"),
            box.y0 - rect.y1 if box.y0 >= rect.y1 else float("inf"),
        )
        side_attached = side_gap <= gap and v_overlap >= max(1.0, 0.25 * min(box.height, rect.height))
        vertical_attached = (
            vertical_gap <= min(gap, 28.0)
            and h_overlap >= max(4.0, 0.20 * min(box.width, rect.width))
        )
        if side_attached or vertical_attached:
            risks.append({
                "kind": "nearby_short_text",
                "text": text,
                "gap": round(min(side_gap, vertical_gap), 2),
            })
    return risks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("assets", type=Path, help="question-bank/assets.json")
    ap.add_argument("--asset-id", required=True)
    ap.add_argument(
        "--confirm-source-neighborhood",
        action="store_true",
        help="assert that the source halo and final file were visually compared",
    )
    ap.add_argument("--method", default="source-page-halo+final-file")
    args = ap.parse_args()

    data = json.loads(args.assets.read_text(encoding="utf-8"))
    assets = data.get("assets") or []
    asset = next((a for a in assets if str(a.get("id")) == args.asset_id), None)
    if asset is None:
        raise SystemExit(f"asset id not found: {args.asset_id}")

    root = args.assets.parent
    file_value = asset.get("file") or asset.get("path")
    if not file_value:
        raise SystemExit("asset has no file/path")
    asset_path = Path(file_value)
    if not asset_path.is_absolute():
        asset_path = root / asset_path
    if not asset_path.is_file():
        raise SystemExit(f"asset file not found: {asset_path}")

    crop = asset.setdefault("crop", {})
    role = asset.get("role")
    source_hash = None
    reviewed_bbox = None

    if role in {"stem", "shared", "answer"}:
        if not args.confirm_source_neighborhood:
            raise SystemExit(
                "stem/shared/answer assets require --confirm-source-neighborhood after "
                "visually comparing the source halo and final file"
            )
        source = asset.get("source") or {}
        if not _valid_bbox(source.get("bbox")):
            raise SystemExit("stem/shared/answer asset requires a valid source.bbox")
        page_no = source.get("page")
        if not isinstance(page_no, int) or page_no < 1:
            raise SystemExit("stem/shared/answer asset requires a positive source.page")
        source_file = source.get("file")
        if not source_file:
            raise SystemExit("stem/shared/answer asset requires source.file")
        source_path = Path(source_file)
        if not source_path.is_absolute():
            source_path = root / source_path
        if not source_path.is_file():
            raise SystemExit(f"source PDF not found: {source_path}")

        doc = fitz.open(source_path)
        if page_no > doc.page_count:
            raise SystemExit(f"source.page {page_no} exceeds {doc.page_count}")
        rect = fitz.Rect(*source["bbox"])
        risks = nearby_text_risks(doc[page_no - 1], rect)
        ignored = {str(v) for v in (crop.get("ignore_nearby_text") or [])}
        unresolved = [
            item for item in risks
            if item["kind"] == "crosses_bbox" or item["text"] not in ignored
        ]
        if unresolved:
            for item in unresolved:
                print(
                    f"UNRESOLVED SOURCE-NEIGHBORHOOD RISK: "
                    f"{item['kind']} {item['text']!r} gap={item.get('gap', 0)}"
                )
            raise SystemExit(
                "review seal refused; enlarge source.bbox or explicitly document "
                "irrelevant nearby text in crop.ignore_nearby_text"
            )
        reviewed_bbox = [float(v) for v in source["bbox"]]
        source_hash = sha256_file(source_path)

    asset["reviewed"] = True
    crop["reviewed"] = True
    crop["review_sha256"] = sha256_file(asset_path)
    crop["review_method"] = args.method
    if role in {"stem", "shared", "answer"}:
        crop["source_neighborhood_reviewed"] = True
        crop["reviewed_source_bbox"] = reviewed_bbox
        crop["review_source_sha256"] = source_hash

    args.assets.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Sealed review for {args.asset_id}: {crop['review_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
