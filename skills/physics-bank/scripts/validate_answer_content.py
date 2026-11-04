#!/usr/bin/env python3
"""Focused QA for canonical answer extraction and solution figure ownership."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("physics_bank_validate_bank", Path(__file__).with_name("validate_bank.py"))
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("questions", type=Path)
    p.add_argument("--assets", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    data = json.loads(args.questions.read_text(encoding="utf-8"))
    assets = json.loads(args.assets.read_text(encoding="utf-8")) if args.assets else {"assets": data.get("assets") or []}
    asset_index = {str(a["id"]): a for a in (assets.get("assets") or []) if a.get("id")}
    questions = data.get("questions") or []
    errors = []
    for question in questions:
        if not isinstance(question, dict):
            errors.append("Non-object question")
        else:
            errors.extend(MOD.validate_answer_content(question, asset_index, strict=True))
            errors.extend(MOD.validate_answer_visual_review(question, asset_index, args.questions.parent, strict=True))
    result = {"status": "ok" if not errors else "error", "errors": errors, "question_count": len(questions)}
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print(f"Answer extraction OK: {len(questions)} question(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
