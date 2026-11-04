#!/usr/bin/env python3
"""Focused validator for canonical Markdown/LaTeX math delimiters in physics-bank questions."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("physics_bank_validate_bank", HERE / "validate_bank.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("questions", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    data = json.loads(args.questions.read_text(encoding="utf-8"))
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise SystemExit("questions.json must contain a top-level questions array")

    errors = []
    for q in questions:
        if not isinstance(q, dict):
            errors.append("questions array contains a non-object entry")
            continue
        qid = str(q.get("id") or "<missing-id>")
        for issue in MOD.question_math_issues(q):
            errors.append(f"{qid}: {issue}")

    result = {
        "status": "ok" if not errors else "error",
        "question_count": len(questions),
        "errors": errors,
    }
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print(f"Math markup OK: {len(questions)} question(s)")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
