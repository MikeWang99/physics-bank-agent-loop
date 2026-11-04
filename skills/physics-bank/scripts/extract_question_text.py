#!/usr/bin/env python3
"""Deterministically extract question drafts from exam PDFs.

This is Stage A of physics-bank v2. It never invents missing text. It records
page/line provenance, question boundaries, shared context, source pages, and
manual-review reasons so later AI enrichment cannot silently hide extraction
uncertainty.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import fitz

QUESTION_PATTERNS = [
    re.compile(r"^\s*(?:Question\s+|Q\s*)?(?P<num>\d{1,3})\s*[.)][:.-]?\s*(?P<rest>.*)$", re.I),
    re.compile(r"^\s*(?:Question\s+|Q\s*)(?P<num>\d{1,3})\s*[:.-]?\s*(?P<rest>.*)$", re.I),
    re.compile(r"^\s*(?P<num>\d{1,3})\s*$"),
]
CHOICE_RE = re.compile(r"^\s*[\[(]?(?P<label>[A-H])[]).:]\s*(?P<text>.*)$")
SHARED_RE = re.compile(
    r"\bquestions?\s+(?P<a>\d{1,3})\s*(?:-|–|—|to|and|&)\s*(?P<b>\d{1,3})\b",
    re.I,
)
SHARED_SIGNAL_RE = re.compile(
    r"\b(?:refer|following|information|diagram|figure|graph|table|passage|data)\b",
    re.I,
)


@dataclass
class Line:
    page: int
    index: int
    text: str
    bbox: list[float]

    @property
    def key(self) -> str:
        return f"p{self.page}:l{self.index}"


def normalize_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00ad", "")).strip()


def page_lines(page: fitz.Page, page_number: int) -> list[Line]:
    rows: list[tuple[float, float, str, list[float]]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            text = normalize_line(text)
            if not text:
                continue
            bbox = [round(float(v), 2) for v in line.get("bbox", (0, 0, 0, 0))]
            rows.append((bbox[1], bbox[0], text, bbox))
    rows.sort(key=lambda item: (item[0], item[1]))
    return [Line(page_number, idx, text, bbox) for idx, (_, _, text, bbox) in enumerate(rows, start=1)]


def question_anchor(text: str):
    for pattern in QUESTION_PATTERNS:
        match = pattern.match(text)
        if match:
            return match.group("num"), (match.groupdict().get("rest") or "").strip()
    return None


def expand_range(a: int, b: int) -> list[str]:
    lo, hi = sorted((a, b))
    if hi - lo > 25:
        return [str(a), str(b)]
    return [str(i) for i in range(lo, hi + 1)]


def split_body(lines: list[str]) -> tuple[str, list[dict[str, str]]]:
    stem_lines: list[str] = []
    choices: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for text in lines:
        match = CHOICE_RE.match(text)
        if match:
            current = {"label": match.group("label"), "text": match.group("text").strip()}
            choices.append(current)
        elif current is not None:
            current["text"] = (current["text"] + " " + text).strip()
        else:
            stem_lines.append(text)
    return "\n".join(stem_lines).strip(), choices


def scan_page_raster_ratio(page: fitz.Page) -> float:
    page_area = max(1.0, page.rect.width * page.rect.height)
    biggest = 0.0
    for image in page.get_images(full=True):
        try:
            for rect in page.get_image_rects(image[0]):
                biggest = max(biggest, rect.width * rect.height)
        except Exception:
            continue
    return min(1.0, biggest / page_area)


def extract(pdf: Path, id_prefix: str) -> dict:
    doc = fitz.open(pdf)
    pages: list[dict] = []
    flat: list[Line] = []
    for page_no, page in enumerate(doc, start=1):
        lines = page_lines(page, page_no)
        flat.extend(lines)
        pages.append({
            "page": page_no,
            "text_char_count": sum(len(line.text) for line in lines),
            "largest_raster_page_ratio": round(scan_page_raster_ratio(page), 3),
            "lines": [asdict(line) | {"key": line.key} for line in lines],
        })

    questions: list[dict] = []
    current: dict | None = None
    preamble: list[Line] = []
    assigned: set[str] = set()
    shared_contexts: list[dict] = []

    def finish_current():
        nonlocal current
        if current is None:
            return
        body_texts = current.pop("_body_texts")
        stem, choices = split_body(body_texts)
        current["stem"] = stem
        current["choices"] = choices
        raw = "\n".join(current.pop("_raw_texts")).strip()
        current["raw_source_text"] = raw
        current["source_text_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        current["source_pages"] = sorted(set(current["source_pages"]))
        reasons = current["review_reasons"]
        if not stem and not current.get("context"):
            reasons.append("empty_stem")
        if raw.endswith(("and", "or", "the", "of", "to", ",", ";", ":")):
            reasons.append("possible_truncated_ending")
        if len(raw) < 15:
            reasons.append("very_short_source_text")
        current["review_reasons"] = sorted(set(reasons))
        current["requires_manual_review"] = bool(current["review_reasons"])
        current["extraction"] = {
            "method": "pdf-text-layer",
            "text_reviewed": False,
            "confidence": 0.55 if current["requires_manual_review"] else 0.9,
            "line_keys": current.pop("_line_keys"),
        }
        questions.append(current)
        current = None

    for line in flat:
        # A shared-stimulus heading can appear between numbered questions. Treat
        # it as pre-question context rather than appending it to the previous
        # question, otherwise questions 5-6 style prompts get swallowed by q4.
        if SHARED_RE.search(line.text) and SHARED_SIGNAL_RE.search(line.text):
            finish_current()
            preamble.append(line)
            continue

        anchor = question_anchor(line.text)
        if anchor:
            finish_current()
            num, rest = anchor
            # Treat accumulated pre-question text as a potential shared stimulus.
            if preamble:
                pre_text = "\n".join(item.text for item in preamble).strip()
                shared_match = SHARED_RE.search(pre_text)
                if shared_match:
                    owners = expand_range(int(shared_match.group("a")), int(shared_match.group("b")))
                    shared_contexts.append({
                        "id": f"shared-{len(shared_contexts)+1:03d}",
                        "text": pre_text,
                        "owners_original_numbers": owners,
                        "source_pages": sorted({item.page for item in preamble}),
                        "line_keys": [item.key for item in preamble],
                    })
                    assigned.update(item.key for item in preamble)
                preamble = []
            qid = f"{id_prefix}-q{int(num):03d}"
            current = {
                "id": qid,
                "original_number": str(int(num)),
                "source": {"file": pdf.name, "page": line.page, "original_number": str(int(num))},
                "source_pages": [line.page],
                "context": "",
                "answer": {"text": None, "label": None, "evidence": "not-provided"},
                "knowledge_points": [],
                "classification": None,
                "asset_ids": [],
                "review_reasons": [],
                "_body_texts": [rest] if rest else [],
                "_raw_texts": [line.text],
                "_line_keys": [line.key],
            }
            assigned.add(line.key)
            continue

        if current is None:
            preamble.append(line)
        else:
            current["source_pages"].append(line.page)
            current["_body_texts"].append(line.text)
            current["_raw_texts"].append(line.text)
            current["_line_keys"].append(line.key)
            assigned.add(line.key)

    finish_current()

    # Attach shared contexts by source question number.
    by_number = {q["original_number"]: q for q in questions}
    for shared in shared_contexts:
        for num in shared["owners_original_numbers"]:
            if num in by_number:
                q = by_number[num]
                q["context"] = shared["text"]
                q["source_pages"] = sorted(set(q["source_pages"] + shared["source_pages"]))
                q.setdefault("shared_context_ids", []).append(shared["id"])

    page_flags: dict[int, list[str]] = {}
    for page in pages:
        flags: list[str] = []
        if page["text_char_count"] < 20 and page["largest_raster_page_ratio"] > 0.6:
            flags.append("scanned_or_image_only_page")
        if flags:
            page_flags[page["page"]] = flags
    for q in questions:
        for page_no in q["source_pages"]:
            q["review_reasons"].extend(page_flags.get(page_no, []))
        q["review_reasons"] = sorted(set(q["review_reasons"]))
        q["requires_manual_review"] = bool(q["review_reasons"])
        q["extraction"]["confidence"] = 0.45 if q["requires_manual_review"] else q["extraction"]["confidence"]

    unassigned = [
        {"page": line.page, "key": line.key, "text": line.text, "bbox": line.bbox}
        for line in flat if line.key not in assigned
    ]
    total_chars = sum(len(line.text) for line in flat)
    unassigned_chars = sum(len(item["text"]) for item in unassigned)
    report = {
        "schema_version": "2.0",
        "source_pdf": str(pdf),
        "page_count": len(doc),
        "question_count": len(questions),
        "shared_contexts": shared_contexts,
        "questions": questions,
        "unassigned_text": unassigned,
        "coverage": {
            "total_text_chars": total_chars,
            "unassigned_text_chars": unassigned_chars,
            "assigned_ratio": round(1 - unassigned_chars / total_chars, 4) if total_chars else 0.0,
        },
        "pages": pages,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--id-prefix", default=None)
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")
    args.outdir.mkdir(parents=True, exist_ok=True)
    prefix = args.id_prefix or re.sub(r"[^a-z0-9]+", "-", args.pdf.stem.lower()).strip("-") or "question"
    result = extract(args.pdf, prefix)
    (args.outdir / "raw_pages.json").write_text(
        json.dumps({"schema_version": "2.0", "source_pdf": result["source_pdf"], "pages": result["pages"]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    draft = {key: value for key, value in result.items() if key != "pages"}
    (args.outdir / "question_drafts.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {result['question_count']} question draft(s); assigned_ratio={result['coverage']['assigned_ratio']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
