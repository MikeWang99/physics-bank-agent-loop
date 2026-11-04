#!/usr/bin/env python3
"""Render exam PDF pages and propose figure candidates without silently losing nearby labels.

Discovery is intentionally conservative: candidates are REVIEW AIDS, not final
assets. Vector/raster geometry is clustered first, then nearby short text labels
(e.g. "12 V", ε, axis symbols) are absorbed before the candidate is rendered.
Final publication assets must still be rendered directly from the source PDF
using their reviewed source bbox.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz

QUESTION_PATTERNS = [
    re.compile(r"^\s*(?:Question\s+|Q\s*)?(\d{1,3})\s*[.)][:.-]?", re.I),
    re.compile(r"^\s*(?:Question\s+|Q\s*)(\d{1,3})\b", re.I),
    re.compile(r"^\s*(\d{1,3})\s*$"),
]


def clusters(rects: list[fitz.Rect], gap_x: float = 18, gap_y: float = 18) -> list[fitz.Rect]:
    parent = list(range(len(rects)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(a, b):
        a, b = root(a), root(b)
        if a != b:
            parent[b] = a

    def nearby(a, b):
        return not (
            a.x1 + gap_x < b.x0
            or b.x1 + gap_x < a.x0
            or a.y1 + gap_y < b.y0
            or b.y1 + gap_y < a.y0
        )

    for i, rect in enumerate(rects):
        for j in range(i):
            if nearby(rect, rects[j]):
                join(i, j)
    grouped = {}
    for i, rect in enumerate(rects):
        key = root(i)
        if key not in grouped:
            grouped[key] = fitz.Rect(rect)
        else:
            grouped[key].include_rect(rect)
    return list(grouped.values())


def graphics_on_page(page: fitz.Page) -> tuple[list[fitz.Rect], bool]:
    """Return candidate graphics and whether a page-sized scan/raster was detected."""
    rects = []
    page_area = page.rect.width * page.rect.height
    full_page_raster = False
    for image in page.get_images(full=True):
        try:
            for rect in page.get_image_rects(image[0]):
                area = rect.width * rect.height
                if area > page_area * 0.70:
                    full_page_raster = True
                    continue
                if rect.width >= 8 and rect.height >= 8:
                    rects.append(fitz.Rect(rect))
        except Exception:
            pass
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        rect = fitz.Rect(rect)
        area = rect.width * rect.height
        if rect.width < 6 or rect.height < 6 or area > page_area * 0.40:
            continue
        fill = drawing.get("fill")
        white_fill = fill is not None and len(fill) >= 3 and all(c >= .92 for c in fill[:3])
        if white_fill and area > page_area * .15:
            continue
        rects.append(rect)
    return rects, full_page_raster


def text_lines(page: fitz.Page) -> list[dict]:
    """Return source text lines with geometry for label-aware discovery."""
    out = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if not text:
                continue
            bbox = fitz.Rect(line.get("bbox", (0, 0, 0, 0)))
            if bbox.is_empty:
                continue
            out.append({"text": text, "bbox": bbox})
    return out


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def nearby_short_labels(
    rect: fitz.Rect,
    lines: list[dict],
    *,
    max_gap: float = 42.0,
    max_chars: int = 24,
) -> list[dict]:
    """Find short text objects geometrically attached to a graphic cluster.

    This deliberately prefers false-positive inclusion over silent omission.
    Candidates can contain a little neighboring text because the final asset is
    cropped later from the ORIGINAL PDF; losing a label at discovery time is
    irreversible if the candidate raster is treated as the source.
    """
    found = []
    for item in lines:
        text = " ".join(str(item["text"]).split())
        box = fitz.Rect(item["bbox"])
        if len(text) > max_chars or box.height > 32:
            continue
        if rect.intersects(box) or rect.contains(box):
            continue

        v_overlap = _overlap(rect.y0, rect.y1, box.y0, box.y1)
        h_overlap = _overlap(rect.x0, rect.x1, box.x0, box.x1)

        left_gap = rect.x0 - box.x1 if box.x1 <= rect.x0 else float("inf")
        right_gap = box.x0 - rect.x1 if box.x0 >= rect.x1 else float("inf")
        side_gap = min(left_gap, right_gap)
        side_attached = (
            side_gap <= max_gap
            and v_overlap >= max(1.0, 0.25 * min(box.height, rect.height))
        )

        top_gap = rect.y0 - box.y1 if box.y1 <= rect.y0 else float("inf")
        bottom_gap = box.y0 - rect.y1 if box.y0 >= rect.y1 else float("inf")
        vertical_gap = min(top_gap, bottom_gap)
        vertical_attached = (
            vertical_gap <= min(max_gap, 28.0)
            and h_overlap >= max(4.0, 0.20 * min(box.width, rect.width))
        )

        if side_attached or vertical_attached:
            found.append({
                "text": text,
                "bbox": [round(v, 2) for v in (box.x0, box.y0, box.x1, box.y1)],
                "gap": round(min(side_gap, vertical_gap), 2),
            })
    return found


def expand_with_labels(rect: fitz.Rect, labels: list[dict]) -> fitz.Rect:
    expanded = fitz.Rect(rect)
    for item in labels:
        expanded.include_rect(fitz.Rect(item["bbox"]))
    return expanded


def anchor_number(text: str):
    for pattern in QUESTION_PATTERNS:
        match = pattern.match(text)
        if match:
            return match.group(1)
    return None


def question_hints(page: fitz.Page) -> list[dict]:
    hints = []
    for item in text_lines(page):
        num = anchor_number(item["text"])
        if num:
            hints.append({"number": num, "y": round(item["bbox"].y0, 2)})
    unique = {(x["number"], x["y"]): x for x in hints}
    return sorted(unique.values(), key=lambda x: x["y"])


def owner_hint(rect, questions):
    preceding = [q for q in questions if q["y"] <= rect.y0 + 2]
    return preceding[-1]["number"] if preceding else None


def parse_pages(value: str | None):
    if not value:
        return None
    selected = set()
    for part in value.split(","):
        lo, _, hi = part.strip().partition("-")
        start, end = int(lo), int(hi or lo)
        selected.update(range(start, end + 1))
    return selected


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--zoom", type=float, default=6.0)
    ap.add_argument("--pages")
    ap.add_argument("--padding", type=float, default=18.0)
    ap.add_argument(
        "--label-gap",
        type=float,
        default=42.0,
        help="max PDF-point gap for absorbing nearby short text labels",
    )
    args = ap.parse_args()
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        raise SystemExit(f"Not a readable PDF: {args.pdf}")

    selected = parse_pages(args.pages)
    pages_dir = args.outdir / "pages"
    cand_dir = args.outdir / "candidates"
    pages_dir.mkdir(parents=True, exist_ok=True)
    cand_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(args.pdf)
    scale = fitz.Matrix(args.zoom, args.zoom)
    manifest = {
        "schema_version": "2.1",
        "source_pdf": str(args.pdf),
        "zoom": args.zoom,
        "padding": args.padding,
        "label_gap": args.label_gap,
        "pages": [],
        "candidates": [],
    }

    for index, page in enumerate(doc, start=1):
        if selected is not None and index not in selected:
            continue

        page_png = pages_dir / f"page-{index:03d}.png"
        page.get_pixmap(matrix=scale, alpha=False).save(page_png)
        rects, full_page_raster = graphics_on_page(page)
        lines = text_lines(page)
        hints = question_hints(page)
        manifest["pages"].append({
            "page": index,
            "render": f"pages/{page_png.name}",
            "full_page_raster_detected": full_page_raster,
            "question_hints": hints,
        })

        for number, graphics_rect in enumerate(clusters(rects), start=1):
            labels = nearby_short_labels(graphics_rect, lines, max_gap=args.label_gap)
            semantic_hint = expand_with_labels(graphics_rect, labels)
            clip = fitz.Rect(
                semantic_hint.x0 - args.padding,
                semantic_hint.y0 - args.padding,
                semantic_hint.x1 + args.padding,
                semantic_hint.y1 + args.padding,
            ) & page.rect
            if clip.width < 12 or clip.height < 12:
                continue

            filename = f"page-{index:03d}-candidate-{number:02d}.png"
            output = cand_dir / filename
            page.get_pixmap(matrix=scale, clip=clip, alpha=False).save(output)
            manifest["candidates"].append({
                "id": f"p{index:03d}-c{number:02d}",
                "file": f"candidates/{filename}",
                "page": index,
                "nearest_question_above_hint": owner_hint(clip, hints),
                "graphics_bbox_pdf_points": [
                    round(v, 2)
                    for v in (graphics_rect.x0, graphics_rect.y0, graphics_rect.x1, graphics_rect.y1)
                ],
                "nearby_text_labels": labels,
                "bbox_pdf_points": [
                    round(v, 2)
                    for v in (clip.x0, clip.y0, clip.x1, clip.y1)
                ],
                "status": "unreviewed",
            })

    (args.outdir / "candidates.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Rendered {len(manifest['pages'])} page(s) and proposed "
        f"{len(manifest['candidates'])} candidate(s): {args.outdir}"
    )


if __name__ == "__main__":
    main()
