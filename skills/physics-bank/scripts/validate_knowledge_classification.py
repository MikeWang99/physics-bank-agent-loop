#!/usr/bin/env python3
"""Strict v2 Knowledge UID / source / independent-review gate; TIMBAD untouched."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
from knowledge_taxonomy import load_knowledge_taxonomy, validate_uid

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("validate_difficulty", ROOT / "validate_difficulty.py")
DIFFICULTY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(DIFFICULTY)

SCHEMA = "physics-question-classification/v2"
SYSTEMS = {"ap-physics-1", "ap-physics-2", "ap-c-mech", "ap-c-em",
           "igcse", "competition", "bpho", "a-level", "physics-bowl"}
LEGACY_PREFIXES = ("course:", "unit:", "topic:", "subtopic:", "domain:",
                   "primary-topic:", "secondary-topic:", "model:", "skill:")

def has_text(v):
    return isinstance(v, str) and bool(v.strip())

def validate_question(q: dict, taxonomy: dict, strict: bool = False) -> list[str]:
    qid = str(q.get("id") or "<missing-id>")
    c = q.get("classification") or {}
    if c.get("schema") != SCHEMA:
        return [f"{qid}: requires {SCHEMA}"]
    errors = []
    def bad(message):
        errors.append(f"{qid}: {message}")
    if q.get("source_system") not in SYSTEMS:
        bad("source_system must be a supported original course/competition source")
    if q.get("source_system") == "competition" and not has_text(q.get("source_event")):
        bad("competition requires source_event (e.g. fma); a generic source is ambiguous")
    uid = c.get("primary_knowledge_uid")
    status = c.get("status")
    if status not in {"proposed", "needs_review", "reviewed"}:
        bad("invalid v2 classification.status")
    if uid is not None and not validate_uid(uid, taxonomy):
        bad("primary_knowledge_uid must exist in the pinned knowledge taxonomy")
    if status == "reviewed" and uid is None:
        bad("reviewed classification requires exactly one primary UID")
    if strict and status != "reviewed":
        bad("strict publication requires reviewed classification")
    if not isinstance(c.get("confidence"), (int, float)) or isinstance(c.get("confidence"), bool) or not 0 <= c["confidence"] <= 1:
        bad("confidence must be a number in [0,1]")
    if strict:
        analysis = c.get("physics_analysis") or {}
        if not (isinstance(analysis.get("required_concepts"), list) and analysis["required_concepts"] and
                all(has_text(x) for x in analysis["required_concepts"]) and
                has_text(analysis.get("solution_summary")) and
                has_text(analysis.get("latest_required_reason"))):
            bad("physics_analysis must explain required concepts, solution, and latest prerequisite")
        candidates = c.get("candidates")
        if not isinstance(candidates, list) or not candidates or not any(
            isinstance(item, dict) and item.get("uid") == uid and item.get("decision") == "selected" for item in candidates
        ):
            bad("candidate comparison must explicitly select the primary UID")
        else:
            for item in candidates:
                if not isinstance(item, dict) or not validate_uid(item.get("uid"), taxonomy):
                    bad("candidate UID is not in taxonomy")
                    continue
                if item.get("decision") not in {"selected", "excluded"} or not has_text(item.get("reason")):
                    bad("each candidate requires a supported decision and concise reason")
                if item.get("decision") == "excluded" and not has_text(item.get("exclusion_reason")):
                    bad("excluded candidates require exclusion_reason")
        review = c.get("review") or {}
        if not (review.get("reviewed") is True and has_text(review.get("method"))
                and review.get("initial_uid") == uid and review.get("independent_uid") == uid
                and review.get("agreement") is True and review.get("cross_chapter_checked") is True):
            bad("strict v2 publication requires agreeing, documented independent review with cross-chapter check")
    stamp = c.get("taxonomy") or {}
    if stamp.get("version") != taxonomy["version"] or stamp.get("sha256") != taxonomy["sha256"]:
        bad("taxonomy version/hash mismatch with validated source")
    difficulty = c.get("difficulty")
    errors.extend(f"{qid}: {e}" for e in DIFFICULTY.validate_difficulty(difficulty, strict=strict))
    if strict:
        if q.get("difficulty") != (difficulty.get("level") if isinstance(difficulty, dict) and difficulty.get("review_status") == "APPROVED" else None):
            bad("difficulty mirror is inconsistent with APPROVED TIMBAD")
        if any(str(t).startswith(LEGACY_PREFIXES) for t in q.get("tags") or []):
            bad("v2 question has legacy generated semantic tags; rederive without erasing custom labels")
        if q.get("requires_manual_review"):
            bad("question still requires manual review")
    return errors

def validate(data: dict, taxonomy: dict, strict: bool = False) -> dict:
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("questions[] is required")
    errors = []
    for q in questions:
        if isinstance(q, dict):
            errors.extend(validate_question(q, taxonomy, strict))
        else:
            errors.append("questions[] contains a non-object item")
    return {"status": "ok" if not errors else "error", "errors": errors, "question_count": len(questions),
            "taxonomy": {"version": taxonomy["version"], "sha256": taxonomy["sha256"], "node_count": taxonomy["count"]}}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", type=Path)
    parser.add_argument("--knowledge-taxonomy", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate(json.loads(args.questions.read_text(encoding="utf-8")),
                      load_knowledge_taxonomy(args.knowledge_taxonomy), args.strict)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for error in report["errors"]:
        print("ERROR:", error)
    return 0 if report["status"] == "ok" else 1

if __name__ == "__main__":
    raise SystemExit(main())
