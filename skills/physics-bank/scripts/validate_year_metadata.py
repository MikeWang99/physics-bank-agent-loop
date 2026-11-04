#!/usr/bin/env python3
"""Validate canonical exam-year metadata in physics-bank question records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(data: dict) -> dict:
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("questions.json must contain a top-level questions array")

    errors: list[str] = []
    for question in questions:
        qid = str(question.get("id") or "<missing-id>")
        year = question.get("year")
        v2 = (question.get("classification") or {}).get("schema") == "physics-question-classification/v2"
        if year is None and v2:
            # Optional source metadata: absence alone is not a publication error.
            if (question.get("source") or {}).get("year") is not None:
                errors.append(f"{qid}: source.year exists but question.year is absent")
            continue
        if type(year) is not int or not (1900 <= year <= 2099):
            errors.append(f"{qid}: missing/invalid year")
            continue

        tags = [str(tag) for tag in (question.get("tags") or [])]
        expected = f"year:{year}"
        if expected not in tags and not v2:
            errors.append(f"{qid}: missing tag {expected}")

        source = question.get("source") if isinstance(question.get("source"), dict) else {}
        source_year = source.get("year")
        if source_year != year:
            errors.append(f"{qid}: source.year {source_year!r} does not match year {year}")

        evidence = question.get("year_evidence")
        if (not v2) and (not isinstance(evidence, dict) or not evidence.get("method") or evidence.get("value") in (None, "")):
            errors.append(f"{qid}: year_evidence is required")

    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "question_count": len(questions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    data = json.loads(args.questions.read_text(encoding="utf-8"))
    report = validate(data)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
