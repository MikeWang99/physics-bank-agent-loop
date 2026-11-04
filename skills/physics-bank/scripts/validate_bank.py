#!/usr/bin/env python3
"""Validate a physics-bank v2 bundle before publishing or downstream export."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import fitz
from PIL import Image


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _mask_nonprose_spans(text: str) -> str:
    """Mask code, URLs, and valid math spans while preserving positions."""
    value = str(text or "")
    def blank(match: re.Match) -> str:
        return " " * len(match.group(0))
    value = re.sub(r"`[^`\n]*`", blank, value)
    value = re.sub(r"https?://\S+", blank, value)
    value = re.sub(r"\$\$.*?\$\$", blank, value, flags=re.S)
    value = re.sub(r"\$[^$\n]+\$", blank, value)
    return value


_BARE_MATH_PATTERNS = [
    re.compile(r"\\[A-Za-z]+_(?:\{[^{}\n]+\}|[A-Za-z0-9+\-]+)"),
    re.compile(r"\\[A-Za-z]+\^(?:\{[^{}\n]+\}|[A-Za-z0-9+\-]+)"),
    re.compile(r"\\[A-Za-z]+"),
    re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-zΑ-Ωα-ωµμ][A-Za-z0-9]*|[0-9]+)_(?:\{[^{}\n]+\}|[A-Za-z0-9+\-]+)"),
    re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-zΑ-Ωα-ωµμ][A-Za-z0-9]*|[0-9]+)\^(?:\{[^{}\n]+\}|[A-Za-z0-9+\-]+)"),
]


def find_bare_math_markup(text: str) -> list[str]:
    """Return unmistakable math syntax that appears outside $...$/$...$."""
    masked = _mask_nonprose_spans(text)
    found: list[str] = []
    for pattern in _BARE_MATH_PATTERNS:
        for match in pattern.finditer(masked):
            token = match.group(0)
            if token not in found:
                found.append(token)
    if "$" in masked:
        found.append("<unmatched-$>")
    return found


def _question_math_fields(question: dict) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    context = str(question.get("context") or "")
    stem = str(question.get("stem") or question.get("stem_markdown") or "")
    if context:
        fields.append(("context", context))
    if stem:
        fields.append(("stem", stem))
    for index, choice in enumerate(question.get("choices") or [], start=1):
        if isinstance(choice, dict):
            text = str(choice.get("text") or choice.get("text_markdown") or "")
            if text:
                label = str(choice.get("label") or index)
                fields.append((f"choice[{label}]", text))
    for key in ("subquestions", "question_parts", "parts"):
        items = question.get(key) or []
        if isinstance(items, list):
            for index, item in enumerate(items, start=1):
                if isinstance(item, dict):
                    text = str(item.get("text") or item.get("stem") or item.get("content") or "")
                else:
                    text = str(item or "")
                if text:
                    fields.append((f"{key}[{index}]", text))
    answer = question.get("answer")
    if isinstance(answer, dict):
        for key in ("text", "sampleAnswer", "explanation"):
            text = str(answer.get(key) or "")
            if text:
                fields.append((f"answer.{key}", text))
        for index, block in enumerate(answer.get("layout_blocks") or [], 1):
            if _layout_kind(block) == "text":
                text = str(block.get("text") or "")
                if text:
                    fields.append((f"answer.layout_blocks[{index}]", text))
    return fields


def question_math_issues(question: dict) -> list[str]:
    issues: list[str] = []
    for field, text in _question_math_fields(question):
        tokens = find_bare_math_markup(text)
        if tokens:
            shown = ", ".join(repr(token) for token in tokens[:8])
            issues.append(
                f"{field} contains bare/unbalanced math markup outside $...$: {shown}; "
                "normalize the canonical bank text to markdown+latex"
            )
    return issues


def _label(value) -> str:
    return str(value or "").strip().upper()


def _layout_kind(block: dict) -> str:
    if not isinstance(block, dict):
        return ""
    if block.get("type"):
        return str(block.get("type") or "").strip().lower()
    if block.get("asset_id"):
        return "figure"
    if block.get("text") is not None:
        return "text"
    return ""


def _normalize_layout_text(value) -> str:
    return " ".join(str(value or "").split())


def _valid_source_bbox(value) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        x0, y0, x1, y1 = (float(v) for v in value)
    except (TypeError, ValueError):
        return False
    return x1 > x0 and y1 > y0



def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _bbox_equal(a, b, tol: float = 0.01) -> bool:
    if not _valid_source_bbox(a) or not _valid_source_bbox(b):
        return False
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def _edge_ink_risk(path: Path, border: int = 2, tol: int = 10) -> tuple[int, int]:
    """Return (dark border pixels, inspected border pixels).

    Final reviewed crops are expected to retain a tiny white safety margin.
    Significant ink touching the outermost border is a generic clipping signal.
    """
    try:
        img = Image.open(path).convert("L")
    except Exception:
        return -1, 0
    w, h = img.size
    if w < 4 or h < 4:
        return -1, 0
    px = img.load()
    coords = set()
    b = min(border, max(1, min(w, h) // 2))
    for y in range(h):
        for x in list(range(b)) + list(range(max(0, w - b), w)):
            coords.add((x, y))
    for x in range(w):
        for y in list(range(b)) + list(range(max(0, h - b), h)):
            coords.add((x, y))
    dark = sum(1 for x, y in coords if px[x, y] < 255 - tol)
    return dark, len(coords)


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


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _source_neighborhood_risks(page: fitz.Page, bbox, gap: float = 42.0) -> list[dict]:
    """Find source objects that make a semantic bbox look incomplete."""
    rect = fitz.Rect(*bbox)
    risks: list[dict] = []

    # Text objects are especially important because PDF diagrams often store
    # labels separately from vector strokes.
    for item in _text_lines(page):
        text = item["text"]
        box = item["bbox"]
        if rect.intersects(box):
            if not rect.contains(box):
                risks.append({"kind": "text_crosses_bbox", "text": text})
            continue
        if len(text) > 24 or box.height > 32:
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

    # A drawing/image that intersects the bbox but extends beyond it is an
    # objective clipping failure, independent of semantics.
    for drawing in page.get_drawings():
        box = drawing.get("rect")
        if box is None:
            continue
        box = fitz.Rect(box)
        if rect.intersects(box) and not rect.contains(box):
            risks.append({"kind": "drawing_crosses_bbox", "text": ""})
    for image_info in page.get_images(full=True):
        try:
            image_rects = page.get_image_rects(image_info[0])
        except Exception:
            image_rects = []
        for box in image_rects:
            box = fitz.Rect(box)
            if rect.intersects(box) and not rect.contains(box):
                risks.append({"kind": "image_crosses_bbox", "text": ""})
    return risks


def _validate_source_anchor(anchor, narrative_text: str) -> str | None:
    if not isinstance(anchor, dict):
        return "source_anchor must be an object"
    relation = str(anchor.get("relation") or "").strip()
    if relation not in {"before", "after", "question_start", "question_end"}:
        return "source_anchor.relation must be before/after/question_start/question_end"
    text = _normalize_layout_text(anchor.get("text"))
    if relation in {"before", "after"}:
        if not text:
            return f"source_anchor.text is required for relation={relation}"
        if text.casefold() not in narrative_text.casefold():
            return f"source_anchor text not found in question narrative: {text!r}"
    return None



def validate_answer_content(question: dict, asset_index: dict, strict: bool) -> list[str]:
    """Check answer-key minimality, provenance isolation and structured image explanations."""
    errors: list[str] = []
    qid = str(question.get("id") or "<missing-id>")
    answer = question.get("answer")
    if not isinstance(answer, dict):
        return errors  # The legacy answer-object requirement is checked by validate().

    kind = answer.get("kind")
    if kind is not None and kind not in {"key_only", "worked_solution", "not_provided"}:
        errors.append(f"{qid}: answer.kind must be key_only/worked_solution/not_provided")
    label = str(answer.get("label") or "").strip().upper()
    explanation = str(answer.get("text") or "").strip()
    answer_ids = [str(v) for v in (answer.get("asset_ids") or [])]
    blocks = answer.get("layout_blocks")
    top_ids = [str(v) for v in (question.get("asset_ids") or [])]
    role_answer_ids = [
        aid for aid in top_ids if (asset_index.get(aid) or {}).get("role") == "answer"
    ]

    if len(answer_ids) != len(set(answer_ids)):
        errors.append(f"{qid}: answer.asset_ids contains duplicate figures")
    if set(answer_ids) != set(role_answer_ids):
        errors.append(
            f"{qid}: answer.asset_ids must equal all answer-role assets owned by the question"
        )

    labels = {
        _label(choice.get("label"))
        for choice in (question.get("choices") or []) if isinstance(choice, dict)
    }
    if label and labels and label not in labels:
        errors.append(f"{qid}: answer.label {label!r} does not match any choice")
    if kind == "not_provided" and (label or explanation or answer_ids):
        errors.append(f"{qid}: not_provided answer must not contain invented content")
    if kind == "key_only" and (not label or explanation or answer_ids or blocks):
        errors.append(
            f"{qid}: key_only answer must contain only the correct label; "
            "source attribution belongs in answer.source/evidence, not answer.text"
        )
    if label and explanation and (
        explanation.upper().strip(". :") == label
        or re.fullmatch(
            r"(?:official\s+)?(?:correct\s+)?(?:answer|option|choice)\s*(?:is|:)?\s*[A-Z]\.?",
            explanation, flags=re.I
        )
        or re.fullmatch(
            r"(?:according to|as (?:provided|stated) by|per)\s+.{1,180}?"
            r"(?:official\s+)?(?:answer|key|solution)\s*(?:is|:)?\s*[A-Z]\.?",
            explanation, flags=re.I
        )
    ):
        errors.append(f"{qid}: answer.text repeats a label or source-attribution boilerplate")
    if kind == "worked_solution" and not (explanation or answer_ids):
        errors.append(f"{qid}: worked_solution has no actual explanation or diagram")
    if kind == "worked_solution" and strict:
        ext = answer.get("extraction")
        if not isinstance(ext, dict) or ext.get("reviewed") is not True or not str(ext.get("method") or ""):
            errors.append(f"{qid}: worked_solution requires reviewed answer.extraction.method")

        source = answer.get("source")
        if not isinstance(source, dict) or not str(source.get("file") or "").strip() or not isinstance(source.get("page"), int) or source.get("page") < 1:
            errors.append(f"{qid}: worked_solution requires answer.source.file and positive answer.source.page")

    for aid in answer_ids:
        asset = asset_index.get(aid)
        if asset is None:
            errors.append(f"{qid}: answer references unknown asset {aid}")
            continue
        if asset.get("role") != "answer":
            errors.append(f"{qid}: answer asset {aid} must use role answer")
        if aid not in top_ids:
            errors.append(f"{qid}: answer asset {aid} must also be in question.asset_ids")
        if [str(v) for v in (asset.get("owners") or [])] != [qid]:
            errors.append(f"{qid}: answer asset {aid} must belong to exactly this question")

    if answer_ids:
        if not isinstance(blocks, list) or not blocks:
            errors.append(f"{qid}: answer figures require ordered answer.layout_blocks")
        else:
            figures = []
            texts = []
            for idx, block in enumerate(blocks, 1):
                typ = _layout_kind(block)
                if typ == "text":
                    value = str(block.get("text") or "").strip()
                    if not value:
                        errors.append(f"{qid}: answer.layout_blocks[{idx}] has empty text")
                    else:
                        texts.append(value)
                elif typ == "figure":
                    aid = str(block.get("asset_id") or "")
                    figures.append(aid)
                    if aid not in answer_ids:
                        errors.append(f"{qid}: answer.layout_blocks[{idx}] references non-answer figure {aid}")
                else:
                    errors.append(f"{qid}: answer.layout_blocks[{idx}] supports text/figure only")
            if sorted(figures) != sorted(answer_ids):
                errors.append(f"{qid}: every answer figure must occur exactly once in answer.layout_blocks")
            if _normalize_layout_text("\n".join(texts)) != _normalize_layout_text(explanation):
                errors.append(f"{qid}: answer.layout_blocks text must reproduce answer.text in order")
            if strict:
                rev = answer.get("layout_review")
                if not isinstance(rev, dict) or rev.get("reviewed") is not True or not str(rev.get("method") or ""):
                    errors.append(f"{qid}: answer.layout_review must be visually reviewed")
    elif blocks:
        if not isinstance(blocks, list) or any(_layout_kind(b) != "text" for b in blocks):
            errors.append(f"{qid}: answer without figures may have only text blocks")
        elif _normalize_layout_text("\n".join(str(b.get("text") or "") for b in blocks)) != _normalize_layout_text(explanation):
            errors.append(f"{qid}: answer.layout_blocks do not match answer.text")

    omissions = answer.get("excluded_non_instructional", [])
    if omissions:
        if not isinstance(omissions, list):
            errors.append(f"{qid}: answer.excluded_non_instructional must be a list")
        else:
            for idx, item in enumerate(omissions, 1):
                if not isinstance(item, dict) or item.get("kind") not in {"signature", "watermark", "page_header", "page_footer", "duplicate_key", "other"}:
                    errors.append(f"{qid}: invalid non-instructional omission #{idx}")
                    continue
                if not str(item.get("reason") or "").strip():
                    errors.append(f"{qid}: non-instructional omission #{idx} requires reason")
                if not _valid_source_bbox(item.get("source_bbox")):
                    errors.append(f"{qid}: non-instructional omission #{idx} requires source_bbox")
            if strict and (answer.get("extraction") or {}).get("reviewed") is not True:
                errors.append(f"{qid}: removed non-instructional marks require reviewed answer.extraction")
    return errors



def _bbox_inside(outer, inner, tol: float = 0.01) -> bool:
    if not _valid_source_bbox(outer) or not _valid_source_bbox(inner):
        return False
    ox0, oy0, ox1, oy1 = map(float, outer)
    ix0, iy0, ix1, iy1 = map(float, inner)
    return (
        ox0 - tol <= ix0 and oy0 - tol <= iy0
        and ix1 <= ox1 + tol and iy1 <= oy1 + tol
    )


def _bbox_overlaps(a, b, tol: float = 0.01) -> bool:
    if not _valid_source_bbox(a) or not _valid_source_bbox(b):
        return False
    ax0, ay0, ax1, ay1 = map(float, a)
    bx0, by0, bx1, by1 = map(float, b)
    return min(ax1, bx1) - max(ax0, bx0) > tol and min(ay1, by1) - max(ay0, by0) > tol


def validate_answer_visual_review(question: dict, asset_index: dict, root: Path, strict: bool) -> list[str]:
    """Validate provenance-bound visual review of source-provided worked solutions.

    This is a machine-checkable *attestation*, not proof of OCR/physics accuracy.
    Reviewing the original and the generated contact sheet remains mandatory.
    """
    qid = str(question.get("id") or "<missing-id>")
    answer = question.get("answer")
    if not isinstance(answer, dict) or answer.get("kind") != "worked_solution" or not strict:
        return []
    errors: list[str] = []
    source = answer.get("source") or {}
    if not isinstance(source, dict):
        source = {}
    source_file = str(source.get("file") or "")
    source_page = source.get("page")
    source_bbox = source.get("bbox")
    review = answer.get("visual_review")
    if not isinstance(review, dict):
        return [f"{qid}: worked_solution requires answer.visual_review sealed against the unchanged answer source"]
    if review.get("reviewed") is not True or not str(review.get("method") or "").strip():
        errors.append(f"{qid}: answer.visual_review requires reviewed=true and method")
    for field in ("instructional_text_complete", "equations_checked", "diagrams_checked"):
        if review.get(field) is not True:
            errors.append(f"{qid}: answer.visual_review.{field} must be confirmed")
    if answer.get("excluded_non_instructional") and review.get("exclusions_checked") is not True:
        errors.append(f"{qid}: answer.visual_review.exclusions_checked required when omitting marks")
    if not _valid_source_bbox(source_bbox):
        errors.append(f"{qid}: worked_solution requires answer.source.bbox for visual coverage")
        return errors
    if review.get("page") != source_page or not _bbox_equal(review.get("bbox"), source_bbox):
        errors.append(f"{qid}: answer.visual_review page/bbox does not match answer.source")
    recorded_hash = str(review.get("source_sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", recorded_hash):
        errors.append(f"{qid}: answer.visual_review.source_sha256 must be a SHA-256 hex digest")
    source_path = root / source_file if source_file and not Path(source_file).is_absolute() else Path(source_file)
    if source_file and source_path.is_file():
        if re.fullmatch(r"[0-9a-f]{64}", recorded_hash) and _sha256_file(source_path) != recorded_hash:
            errors.append(f"{qid}: answer source changed after visual review (source_sha256 mismatch)")
        try:
            doc = fitz.open(source_path)
            if not isinstance(source_page, int) or not 1 <= source_page <= doc.page_count:
                errors.append(f"{qid}: answer.source.page is outside original answer source")
            elif not _bbox_inside(list(doc[source_page - 1].rect), source_bbox):
                errors.append(f"{qid}: answer.source.bbox extends outside original answer page")
            doc.close()
        except Exception as exc:
            errors.append(f"{qid}: cannot inspect original answer source: {exc}")
    else:
        errors.append(f"{qid}: original answer source file is missing: {source_file!r}")
    # Excluded marks may NEVER erase instructional answer diagrams, or lie on another page.
    for idx, omission in enumerate(answer.get("excluded_non_instructional") or [], 1):
        if not isinstance(omission, dict):
            continue
        box = omission.get("source_bbox")
        if not _bbox_inside(source_bbox, box):
            errors.append(f"{qid}: omitted mark #{idx} is outside answer.source.bbox")
            continue
        for aid in answer.get("asset_ids") or []:
            asset = asset_index.get(str(aid)) or {}
            a_source = asset.get("source") or {}
            if a_source.get("file") != source_file or a_source.get("page") != source_page:
                continue
            if _bbox_overlaps(box, a_source.get("bbox")):
                errors.append(
                    f"{qid}: omitted mark #{idx} overlaps instructional answer diagram {aid}; "
                    "manual review required, do not erase diagram content"
                )
    # Keep answer figures within the reviewed source region when they come from the same page.
    for aid in answer.get("asset_ids") or []:
        asset = asset_index.get(str(aid)) or {}
        a_source = asset.get("source") or {}
        if a_source.get("file") == source_file and a_source.get("page") == source_page:
            if not _bbox_inside(source_bbox, a_source.get("bbox")):
                errors.append(f"{qid}: answer diagram {aid} lies outside reviewed answer.source.bbox")
    return errors


def validate(questions_path: Path, assets_path: Path | None, strict: bool, require_text_review: bool) -> dict:
    root = questions_path.parent
    data = load_json(questions_path)
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("questions.json must contain a top-level questions array")
    asset_data = load_json(assets_path) if assets_path and assets_path.exists() else {"assets": data.get("assets", [])}
    assets = asset_data.get("assets", [])
    asset_ids = [str(a.get("id")) for a in assets if a.get("id")]
    asset_index = {str(a.get("id")): a for a in assets if a.get("id")}

    errors: list[str] = []
    warnings: list[str] = []
    if len(asset_ids) != len(set(asset_ids)):
        errors.append("duplicate asset ids")

    seen: set[str] = set()
    question_choice_labels: dict[str, set[str]] = {}
    question_choice_entries: dict[str, dict[str, dict]] = {}
    referenced_asset_ids: set[str] = set()
    choice_pairs: dict[tuple[str, str, int], str] = {}
    choice_files: dict[str, str] = {}

    for q in questions:
        qid = str(q.get("id") or "")
        if not qid:
            errors.append("question missing id")
            continue
        if qid in seen:
            errors.append(f"duplicate question id: {qid}")
        seen.add(qid)
        if strict and q.get("content_format") != "markdown+latex":
            errors.append(f"{qid}: content_format must be markdown+latex")
        if not isinstance(q.get("answer"), dict):
            errors.append(f"{qid}: answer object is required")
        errors.extend(validate_answer_content(q, asset_index, strict))
        errors.extend(validate_answer_visual_review(q, asset_index, root, strict))
        answer_source = (q.get("answer") or {}).get("source") if isinstance(q.get("answer"), dict) else None
        if strict and isinstance(answer_source, dict) and answer_source.get("file"):
            file_value = str(answer_source["file"])
            source_path = Path(file_value) if Path(file_value).is_absolute() else root / file_value
            if not source_path.is_file():
                errors.append(f"{qid}: answer source document does not exist: {file_value}")
        stem = str(q.get("stem") or q.get("stem_markdown") or "").strip()
        context = str(q.get("context") or "").strip()
        if not stem and not context:
            errors.append(f"{qid}: empty stem/context")
        pages = q.get("source_pages") or []
        if not pages:
            source = q.get("source") or {}
            if source.get("page"):
                pages = [source["page"]]
            else:
                errors.append(f"{qid}: missing source_pages/source.page")
        extraction = q.get("extraction") or {}
        if require_text_review and not extraction.get("text_reviewed"):
            errors.append(f"{qid}: extraction.text_reviewed is not true")
        if q.get("requires_manual_review"):
            msg = f"{qid}: requires_manual_review ({', '.join(q.get('review_reasons') or [])})"
            (errors if strict else warnings).append(msg)

        math_issues = question_math_issues(q)
        if math_issues:
            target = errors if strict else warnings
            target.extend(f"{qid}: {issue}" for issue in math_issues)

        choices = q.get("choices") or []
        labels = [_label(c.get("label")) for c in choices if isinstance(c, dict) and c.get("label")]
        if labels and len(set(labels)) != len(labels):
            errors.append(f"{qid}: duplicate choice labels")
        question_choice_labels[qid] = set(labels)
        question_choice_entries[qid] = {
            _label(c.get("label")): c for c in choices if isinstance(c, dict) and c.get("label")
        }

        top_ids = [str(v) for v in (q.get("asset_ids") or [])]
        stem_shared_ids = [
            aid for aid in top_ids
            if (asset_index.get(aid) or {}).get("role") in {"stem", "shared"}
        ]
        layout_blocks = q.get("layout_blocks")
        if strict and stem_shared_ids and not layout_blocks:
            errors.append(f"{qid}: stem/shared visual assets require explicit layout_blocks in v2.3 strict mode")
        if layout_blocks not in (None, ""):
            if not isinstance(layout_blocks, list) or not layout_blocks:
                errors.append(f"{qid}: layout_blocks must be a non-empty list when provided")
            else:
                placed_figures: list[str] = []
                layout_text_parts: list[str] = []
                narrative_text = _normalize_layout_text("\n".join(v for v in (context, stem) if v))
                for idx, block in enumerate(layout_blocks, start=1):
                    kind = _layout_kind(block)
                    if kind == "text":
                        text_value = str(block.get("text") or "").strip() if isinstance(block, dict) else ""
                        if not text_value:
                            errors.append(f"{qid}: layout block {idx} text is empty")
                        else:
                            layout_text_parts.append(text_value)
                    elif kind == "figure":
                        asset_id = str(block.get("asset_id") or "") if isinstance(block, dict) else ""
                        if not asset_id:
                            errors.append(f"{qid}: layout block {idx} figure missing asset_id")
                            continue
                        asset = asset_index.get(asset_id)
                        if asset is None:
                            errors.append(f"{qid}: layout block {idx} references unknown asset {asset_id}")
                            continue
                        if asset_id not in top_ids:
                            errors.append(f"{qid}: layout figure {asset_id} must also appear in question.asset_ids")
                        if asset.get("role") not in {"stem", "shared"}:
                            errors.append(f"{qid}: layout figure {asset_id} must have role stem/shared")
                        placed_figures.append(asset_id)
                        if strict:
                            anchor_error = _validate_source_anchor(block.get("source_anchor"), narrative_text)
                            if anchor_error:
                                errors.append(f"{qid}: layout figure {asset_id}: {anchor_error}")
                    else:
                        errors.append(f"{qid}: layout block {idx} has unsupported type {kind!r}; bank layouts use text/figure only")

                if len(placed_figures) != len(set(placed_figures)):
                    errors.append(f"{qid}: each stem/shared figure may appear only once in layout_blocks")
                if set(placed_figures) != set(stem_shared_ids):
                    missing = sorted(set(stem_shared_ids) - set(placed_figures))
                    extra = sorted(set(placed_figures) - set(stem_shared_ids))
                    details = []
                    if missing:
                        details.append("missing " + ", ".join(missing))
                    if extra:
                        details.append("unexpected " + ", ".join(extra))
                    errors.append(f"{qid}: layout figure coverage mismatch ({'; '.join(details)})")
                layout_text = _normalize_layout_text("\n".join(layout_text_parts))
                if narrative_text and layout_text != narrative_text:
                    errors.append(f"{qid}: layout text blocks must preserve the complete context + stem in order")

                if strict:
                    review = q.get("layout_review")
                    if not isinstance(review, dict) or review.get("reviewed") is not True:
                        errors.append(f"{qid}: layout_review.reviewed must be true")
                    elif not str(review.get("method") or "").strip():
                        errors.append(f"{qid}: layout_review.method is required")

        for choice in choices:
            if not isinstance(choice, dict):
                continue
            label = _label(choice.get("label"))
            for aid in [str(v) for v in (choice.get("asset_ids") or [])]:
                asset = asset_index.get(aid)
                if asset is None:
                    errors.append(f"{qid} choice {label}: missing asset record {aid}")
                    continue
                if asset.get("role") != "choice":
                    errors.append(f"{qid} choice {label}: {aid} is not a choice asset")
                if _label(asset.get("choice_label")) != label:
                    errors.append(f"{qid} choice {label}: {aid} has mismatched choice_label")
                if qid not in [str(v) for v in (asset.get("owners") or [])]:
                    errors.append(f"{qid} choice {label}: {aid} does not belong to this question")
                if aid not in top_ids:
                    errors.append(f"{qid} choice {label}: {aid} must also appear in question.asset_ids")

        for asset_id in top_ids:
            referenced_asset_ids.add(asset_id)
            asset = asset_index.get(asset_id)
            if asset is None:
                errors.append(f"{qid}: missing asset record {asset_id}")
                continue
            file_value = asset.get("file") or asset.get("path")
            asset_path = None
            if not file_value:
                errors.append(f"{asset_id}: asset has no file/path")
            else:
                asset_path = Path(file_value) if Path(file_value).is_absolute() else root / file_value
                if not asset_path.exists():
                    errors.append(f"{asset_id}: asset file not found: {file_value}")
            if not asset.get("reviewed", asset.get("crop", {}).get("reviewed", False)):
                errors.append(f"{asset_id}: final asset not visually reviewed")

            crop_meta = asset.get("crop") or {}
            if strict and asset_path is not None and asset_path.exists():
                review_hash = str(crop_meta.get("review_sha256") or "").strip().lower()
                if not re.fullmatch(r"[0-9a-f]{64}", review_hash):
                    errors.append(
                        f"{asset_id}: strict visual review requires crop.review_sha256; "
                        f"seal the final file after inspection"
                    )
                elif _sha256_file(asset_path) != review_hash:
                    errors.append(
                        f"{asset_id}: final asset changed after visual review "
                        f"(crop.review_sha256 mismatch)"
                    )
                dark, inspected = _edge_ink_risk(asset_path)
                if dark < 0:
                    errors.append(f"{asset_id}: final asset is not a readable image")
                elif dark > max(4, int(inspected * 0.01)):
                    errors.append(
                        f"{asset_id}: {dark} ink pixel(s) touch the outer 2px border; "
                        f"possible clipped label/line — widen the source bbox"
                    )
            owners = [str(v) for v in (asset.get("owners") or [])]
            if owners and qid not in owners:
                errors.append(f"{asset_id}: owners does not include {qid}")
            role = asset.get("role")
            if role not in {"stem", "choice", "shared", "answer"}:
                errors.append(f"{asset_id}: invalid asset role {role!r}")

            if strict and role in {"stem", "shared", "answer"}:
                source_meta = asset.get("source") or {}
                if not isinstance(source_meta, dict):
                    errors.append(f"{asset_id}: source must be an object")
                else:
                    if not str(source_meta.get("file") or "").strip():
                        errors.append(f"{asset_id}: source.file is required for stem/shared/answer visual provenance")
                    page = source_meta.get("page")
                    if not isinstance(page, int) or page < 1:
                        errors.append(f"{asset_id}: source.page must be a positive integer")
                    elif role in {"stem", "shared"} and pages and page not in {int(v) for v in pages if str(v).isdigit()}:
                        errors.append(f"{asset_id}: source.page {page} is not included in {qid}.source_pages")
                    bbox = source_meta.get("bbox")
                    if not _valid_source_bbox(bbox):
                        errors.append(f"{asset_id}: source.bbox must be [x0,y0,x1,y1] with positive area")
                    else:
                        reviewed_bbox = crop_meta.get("reviewed_source_bbox")
                        if not _bbox_equal(reviewed_bbox, bbox):
                            errors.append(
                                f"{asset_id}: crop.reviewed_source_bbox must match the current source.bbox"
                            )
                    if crop_meta.get("source_neighborhood_reviewed") is not True:
                        errors.append(
                            f"{asset_id}: source neighborhood has not been explicitly reviewed"
                        )

                    source_file = str(source_meta.get("file") or "").strip()
                    source_path = None
                    if source_file:
                        source_path = Path(source_file) if Path(source_file).is_absolute() else root / source_file
                        if not source_path.is_file():
                            errors.append(f"{asset_id}: source document not found: {source_file}")
                    if source_path is not None and source_path.is_file():
                        source_hash = str(crop_meta.get("review_source_sha256") or "").strip().lower()
                        if not re.fullmatch(r"[0-9a-f]{64}", source_hash):
                            errors.append(
                                f"{asset_id}: crop.review_source_sha256 is required for stem/shared/answer review"
                            )
                        elif _sha256_file(source_path) != source_hash:
                            errors.append(
                                f"{asset_id}: source PDF changed after visual review "
                                f"(crop.review_source_sha256 mismatch)"
                            )
                        try:
                            doc = fitz.open(source_path)
                            if isinstance(page, int) and 1 <= page <= doc.page_count and _valid_source_bbox(bbox):
                                page_obj = doc[page - 1]
                                rect = fitz.Rect(*bbox)
                                if not page_obj.rect.contains(rect):
                                    errors.append(f"{asset_id}: source.bbox extends outside source page")
                                risks = _source_neighborhood_risks(page_obj, bbox)
                                ignored = {str(v) for v in (crop_meta.get("ignore_nearby_text") or [])}
                                for risk in risks:
                                    if (
                                        risk["kind"] == "nearby_short_text"
                                        and risk.get("text") in ignored
                                    ):
                                        continue
                                    if risk["kind"] == "nearby_short_text":
                                        errors.append(
                                            f"{asset_id}: possible omitted diagram label just outside source.bbox: "
                                            f"{risk.get('text')!r} (gap {risk.get('gap')} pt); "
                                            f"widen bbox or document it in crop.ignore_nearby_text"
                                        )
                                    else:
                                        errors.append(
                                            f"{asset_id}: source object crosses source.bbox "
                                            f"({risk['kind']}{': ' + repr(risk.get('text')) if risk.get('text') else ''})"
                                        )
                        except Exception as exc:
                            errors.append(f"{asset_id}: failed source visual-integrity check: {exc}")

            if role == "answer":
                rel = Path(str(file_value or ""))
                if (rel.is_absolute() or rel.parent != Path("assets") / "answers" / qid
                        or not rel.stem):
                    errors.append(
                        f"{asset_id}: answer asset must live at assets/answers/{qid}/<name>.<ext>"
                    )
                if len(owners) != 1:
                    errors.append(f"{asset_id}: answer asset must have exactly one owner")
                if asset_id not in [str(v) for v in ((q.get("answer") or {}).get("asset_ids") or [])]:
                    errors.append(f"{asset_id}: answer.asset_ids must reference the answer figure")
            if role == "choice":
                label = _label(asset.get("choice_label"))
                index = asset.get("choice_index", 1)
                if len(owners) != 1:
                    errors.append(f"{asset_id}: choice asset must have exactly one owner")
                if not label:
                    errors.append(f"{asset_id}: choice asset missing choice_label")
                elif labels and label not in set(labels):
                    errors.append(f"{asset_id}: choice_label {label!r} does not match a choice in {qid}")
                if not isinstance(index, int) or index < 1:
                    errors.append(f"{asset_id}: choice_index must be a positive integer")
                crop = asset.get("crop") or {}
                if crop.get("isolated_choice") is not True:
                    errors.append(f"{asset_id}: crop.isolated_choice must be true for final choice assets")
                if file_value and len(owners) == 1 and label and isinstance(index, int) and index > 0:
                    rel = Path(str(file_value))
                    expected_parent = Path("assets") / "choices" / owners[0]
                    expected_stem = f"{label}-{index:02d}"
                    if rel.is_absolute() or rel.parent != expected_parent or rel.stem != expected_stem:
                        errors.append(
                            f"{asset_id}: choice asset must live at assets/choices/{owners[0]}/{expected_stem}.<ext>"
                        )
                    key = (owners[0], label, index)
                    prev = choice_pairs.get(key)
                    if prev and prev != asset_id:
                        errors.append(f"{asset_id}: duplicate choice asset slot {owners[0]} {label}-{index:02d} (also {prev})")
                    choice_pairs[key] = asset_id
                    normalized_file = rel.as_posix()
                    prev_file = choice_files.get(normalized_file)
                    if prev_file and prev_file != asset_id:
                        errors.append(f"{asset_id}: choice asset file is also used by {prev_file}")
                    choice_files[normalized_file] = asset_id
                    entry = question_choice_entries.get(qid, {}).get(label)
                    if entry is not None and asset_id not in [str(v) for v in (entry.get("asset_ids") or [])]:
                        errors.append(f"{asset_id}: matching choice {qid}/{label} must reference it in choices[].asset_ids")

    question_ids = seen
    for asset in assets:
        aid = str(asset.get("id") or "<unnamed asset>")
        owners = [str(v) for v in (asset.get("owners") or asset.get("shared_with") or [])]
        if not owners:
            warnings.append(f"{aid}: orphan asset has no owners")
        for owner in owners:
            if owner not in question_ids:
                errors.append(f"{aid}: unknown owner question {owner}")
        role = asset.get("role")
        if role not in {"stem", "choice", "shared", "answer"}:
            errors.append(f"{aid}: invalid asset role {role!r}")
        if aid not in referenced_asset_ids and owners:
            warnings.append(f"{aid}: asset has owners but no question references its id")

    report = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "question_count": len(questions),
        "asset_count": len(assets),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", type=Path)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-text-review", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate(args.questions, args.assets, args.strict, args.require_text_review)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
