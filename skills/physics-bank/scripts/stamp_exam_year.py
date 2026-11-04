#!/usr/bin/env python3
"""Stamp canonical exam-year metadata onto physics-bank question records.

The canonical field is ``year`` (four-digit integer). A matching ``year:YYYY``
tag is also added for simple filtering. Year inference is deliberately
conservative: explicit ``--year`` wins; otherwise a unique year is inferred from
the source filename/top-level source path. Ambiguous or missing years are marked
for manual review instead of guessed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FOUR_DIGIT_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
TWO_DIGIT_RE = re.compile(r"(?<!\d)(\d{2})(?!\d)")
EXAM_HINT_RE = re.compile(r"(?:exam|paper|fma|bpho|physics|round|contest|test|olympiad)", re.I)


def _valid_year(value: int) -> bool:
    return 1900 <= value <= 2099


def infer_year(value: str) -> tuple[int | None, dict | None, str | None]:
    """Return (year, evidence, error_reason) for one source string."""
    text = str(value or "")
    if not text:
        return None, None, "missing_exam_year"

    four = sorted({int(match.group(1)) for match in FOUR_DIGIT_RE.finditer(text)})
    if len(four) == 1:
        year = four[0]
        return year, {"method": "source-four-digit", "value": text}, None
    if len(four) > 1:
        return None, None, "ambiguous_exam_year"

    # Two-digit years are accepted only in an exam-like filename/path, and only
    # in the modern 2000-2039 range. This supports names such as Fma_16_exam.pdf
    # without turning arbitrary question numbers into years.
    if EXAM_HINT_RE.search(text):
        two = sorted({int(match.group(1)) for match in TWO_DIGIT_RE.finditer(text) if 0 <= int(match.group(1)) <= 39})
        if len(two) == 1:
            year = 2000 + two[0]
            return year, {"method": "source-two-digit", "value": text}, None
        if len(two) > 1:
            return None, None, "ambiguous_exam_year"

    return None, None, "missing_exam_year"


def add_review_reason(question: dict, reason: str) -> None:
    reasons = [str(item) for item in (question.get("review_reasons") or [])]
    if reason not in reasons:
        reasons.append(reason)
    question["review_reasons"] = sorted(set(reasons))
    question["requires_manual_review"] = True


def clear_year_review_reasons(question: dict) -> None:
    reasons = [
        str(item) for item in (question.get("review_reasons") or [])
        if str(item) not in {"missing_exam_year", "ambiguous_exam_year", "invalid_exam_year"}
    ]
    question["review_reasons"] = reasons
    question["requires_manual_review"] = bool(reasons)


def stamp(data: dict, explicit_year: int | None = None) -> dict:
    if explicit_year is not None and not _valid_year(explicit_year):
        raise ValueError("--year must be a four-digit year between 1900 and 2099")

    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("input JSON must contain a top-level questions array")

    top_source = str(data.get("source_pdf") or data.get("source", "") or "")
    stamped = 0
    unresolved = 0

    for question in questions:
        source = question.get("source") if isinstance(question.get("source"), dict) else {}
        source_value = str(source.get("file") or source.get("document") or top_source or "")

        if explicit_year is not None:
            year = explicit_year
            evidence = {"method": "explicit", "value": str(explicit_year)}
            reason = None
        else:
            year, evidence, reason = infer_year(source_value)
            if year is None and top_source and top_source != source_value:
                year, evidence, reason = infer_year(top_source)

        if year is None and (question.get("classification") or {}).get("schema") == "physics-question-classification/v2":
            # Do not invent years or mark a verified question unpublishable solely for an absent year.
            clear_year_review_reasons(question)
            if question.get("year") is None:
                question.pop("year", None)
            unresolved += 1
            continue

        if year is None:
            question["year"] = None
            question.pop("year_evidence", None)
            source.pop("year", None)
            add_review_reason(question, reason or "missing_exam_year")
            unresolved += 1
            continue

        clear_year_review_reasons(question)
        question["year"] = year
        question["year_evidence"] = evidence
        source["year"] = year
        question["source"] = source
        tags = [str(tag) for tag in (question.get("tags") or []) if not str(tag).startswith("year:")]
        if (question.get("classification") or {}).get("schema") != "physics-question-classification/v2":
            tags.append(f"year:{year}")
        question["tags"] = tags
        stamped += 1

    data.setdefault("metadata", {})
    if isinstance(data["metadata"], dict):
        data["metadata"]["year_metadata_version"] = "1.0"
    data["year_stamp_summary"] = {"stamped": stamped, "unresolved": unresolved}
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="defaults to updating the input file in place")
    parser.add_argument("--year", type=int, help="explicit exam year override, e.g. 2016")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = stamp(data, args.year)
    output = args.output or args.input
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = result["year_stamp_summary"]
    print(f"Stamped exam year on {summary['stamped']} question(s); unresolved={summary['unresolved']}")
    return 0  # A missing source year is no longer a processing blocker for v2


if __name__ == "__main__":
    raise SystemExit(main())
