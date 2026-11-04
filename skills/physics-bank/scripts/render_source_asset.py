#!/usr/bin/env python3
"""Render a final figure directly from the original PDF source bbox.

This is the publication path for stem/shared assets. Discovery candidates are
only hints and must never become the irreversible parent raster for a final
asset. The command also emits a halo preview showing the kept bbox in context,
so labels just outside the box are visible during review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw


def _rect(values) -> fitz.Rect:
    if len(values) != 4:
        raise ValueError("bbox must have four values: x0 y0 x1 y1")
    rect = fitz.Rect(*(float(v) for v in values))
    if rect.width <= 0 or rect.height <= 0:
        raise ValueError("bbox must have positive area")
    return rect


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


def _nearby_text_risks(page: fitz.Page, rect: fitz.Rect, gap: float = 42.0) -> list[dict]:
    risks = []
    for item in _text_lines(page):
        text = item["text"]
        box = item["bbox"]
        if len(text) > 24 or box.height > 32:
            continue

        if rect.intersects(box):
            if not rect.contains(box):
                risks.append({
                    "kind": "crosses_bbox",
                    "text": text,
                    "bbox": [round(v, 2) for v in (box.x0, box.y0, box.x1, box.y1)],
                    "gap": 0.0,
                })
            continue

        v_overlap = _overlap(rect.y0, rect.y1, box.y0, box.y1)
        h_overlap = _overlap(rect.x0, rect.x1, box.x0, box.x1)
        left_gap = rect.x0 - box.x1 if box.x1 <= rect.x0 else float("inf")
        right_gap = box.x0 - rect.x1 if box.x0 >= rect.x1 else float("inf")
        side_gap = min(left_gap, right_gap)
        top_gap = rect.y0 - box.y1 if box.y1 <= rect.y0 else float("inf")
        bottom_gap = box.y0 - rect.y1 if box.y0 >= rect.y1 else float("inf")
        vertical_gap = min(top_gap, bottom_gap)

        side_attached = (
            side_gap <= gap
            and v_overlap >= max(1.0, 0.25 * min(box.height, rect.height))
        )
        vertical_attached = (
            vertical_gap <= min(gap, 28.0)
            and h_overlap >= max(4.0, 0.20 * min(box.width, rect.width))
        )
        if side_attached or vertical_attached:
            risks.append({
                "kind": "nearby_short_text",
                "text": text,
                "bbox": [round(v, 2) for v in (box.x0, box.y0, box.x1, box.y1)],
                "gap": round(min(side_gap, vertical_gap), 2),
            })
    return risks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--page", type=int, required=True, help="1-based PDF page number")
    ap.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--zoom", type=float, default=6.0)
    ap.add_argument("--halo", type=float, default=48.0, help="PDF points shown around bbox in review preview")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"source PDF not found: {args.pdf}")
    doc = fitz.open(args.pdf)
    if args.page < 1 or args.page > doc.page_count:
        raise SystemExit(f"page {args.page} outside 1..{doc.page_count}")

    page = doc[args.page - 1]
    bbox = _rect(args.bbox) & page.rect
    if bbox.width <= 0 or bbox.height <= 0:
        raise SystemExit("bbox lies outside page")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    matrix = fitz.Matrix(args.zoom, args.zoom)
    page.get_pixmap(matrix=matrix, clip=bbox, alpha=False).save(args.output)

    halo = fitz.Rect(
        bbox.x0 - args.halo,
        bbox.y0 - args.halo,
        bbox.x1 + args.halo,
        bbox.y1 + args.halo,
    ) & page.rect
    debug = args.output.parent / "_debug"
    debug.mkdir(exist_ok=True)
    halo_path = debug / f"{args.output.stem}.source-halo.png"
    page.get_pixmap(matrix=matrix, clip=halo, alpha=False).save(halo_path)

    img = Image.open(halo_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    x0 = int(round((bbox.x0 - halo.x0) * args.zoom))
    y0 = int(round((bbox.y0 - halo.y0) * args.zoom))
    x1 = int(round((bbox.x1 - halo.x0) * args.zoom)) - 1
    y1 = int(round((bbox.y1 - halo.y0) * args.zoom)) - 1
    for offset in range(3):
        draw.rectangle(
            [max(0, x0 - offset), max(0, y0 - offset), min(img.width - 1, x1 + offset), min(img.height - 1, y1 + offset)],
            outline=(220, 30, 30),
        )
    img.save(halo_path)

    risks = _nearby_text_risks(page, bbox)
    report = {
        "source_pdf": str(args.pdf),
        "page": args.page,
        "bbox": [round(v, 2) for v in (bbox.x0, bbox.y0, bbox.x1, bbox.y1)],
        "output": str(args.output),
        "halo_preview": str(halo_path),
        "nearby_text_risks": risks,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Rendered final asset from source PDF: {args.output}")
    print(f"Review halo: {halo_path}")
    if risks:
        print("NEARBY TEXT RISK(S):")
        for item in risks:
            print(f"  {item['kind']}: {item['text']!r} bbox={item['bbox']} gap={item['gap']}")
        print("Do not seal review until every risk is included or explicitly justified in crop.ignore_nearby_text.")
        return 2
    print("No nearby short-text risk detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
