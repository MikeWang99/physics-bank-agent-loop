#!/usr/bin/env python3
"""Validate physics-bank semantic classification against controlled and bank-level taxonomies."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
_spec = importlib.util.spec_from_file_location("derive_semantic_tags", SCRIPT_DIR / "derive_semantic_tags.py")
DERIVE = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(DERIVE)

_difficulty_spec = importlib.util.spec_from_file_location("validate_difficulty", SCRIPT_DIR / "validate_difficulty.py")
DIFFICULTY = importlib.util.module_from_spec(_difficulty_spec)
assert _difficulty_spec.loader is not None
_difficulty_spec.loader.exec_module(DIFFICULTY)

from knowledge_taxonomy import load_knowledge_taxonomy
import validate_knowledge_classification as KNOWLEDGE

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KNOWLEDGE_ROLES = {"required", "supporting", "extension"}
MODEL_ROLES = {"primary", "secondary"}


def _nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unique_ids(items: list[dict], label: str, errors: list[str]) -> None:
    seen = set()
    for item in items:
        iid = str(item.get("id") or "")
        if not iid:
            errors.append(f"{label}: missing id")
        elif not SLUG_RE.fullmatch(iid):
            errors.append(f"{label}: invalid id slug {iid!r}")
        elif iid in seen:
            errors.append(f"{label}: duplicate id {iid}")
        seen.add(iid)


def validate_taxonomy(taxonomy: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    if taxonomy.get("schema") != "physics-bank-curriculum-taxonomy/v1":
        errors.append("taxonomy: schema must be physics-bank-curriculum-taxonomy/v1")
    course = taxonomy.get("course")
    if not isinstance(course, dict):
        errors.append("taxonomy: course must be an object")
        course = {}
    if not _nonempty(course.get("id")) or not SLUG_RE.fullmatch(str(course.get("id") or "")):
        errors.append("taxonomy: course.id must be a stable lowercase slug")
    if not _nonempty(course.get("name")):
        errors.append("taxonomy: course.name is required")
    if not _nonempty(course.get("basis")):
        errors.append("taxonomy: course.basis is required")

    units = taxonomy.get("units")
    if not isinstance(units, list) or not units:
        errors.append("taxonomy: units must be a non-empty array")
        units = []
    _unique_ids([u for u in units if isinstance(u, dict)], "taxonomy unit", errors)
    unit_map, topic_map, sub_map = {}, {}, {}
    for unit in units:
        if not isinstance(unit, dict):
            errors.append("taxonomy: each unit must be an object")
            continue
        uid = str(unit.get("id") or "")
        if not _nonempty(unit.get("name")):
            errors.append(f"taxonomy unit {uid}: name is required")
        unit_map[uid] = unit
        topics = unit.get("topics")
        if not isinstance(topics, list) or not topics:
            errors.append(f"taxonomy unit {uid}: topics must be non-empty")
            topics = []
        _unique_ids([t for t in topics if isinstance(t, dict)], f"taxonomy unit {uid} topic", errors)
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            tid = str(topic.get("id") or "")
            if tid in topic_map:
                errors.append(f"taxonomy: topic id {tid} must be globally unique")
            topic_map[tid] = (uid, topic)
            if not _nonempty(topic.get("name")):
                errors.append(f"taxonomy topic {tid}: name is required")
            subs = topic.get("subtopics") or []
            if not isinstance(subs, list):
                errors.append(f"taxonomy topic {tid}: subtopics must be an array")
                subs = []
            _unique_ids([s for s in subs if isinstance(s, dict)], f"taxonomy topic {tid} subtopic", errors)
            for sub in subs:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "")
                if sid in sub_map:
                    errors.append(f"taxonomy: subtopic id {sid} must be globally unique")
                sub_map[sid] = (uid, tid, sub)
                if not _nonempty(sub.get("name")):
                    errors.append(f"taxonomy subtopic {sid}: name is required")
    return errors, {"course": course, "units": unit_map, "topics": topic_map, "subtopics": sub_map}


def validate_question(q: dict, idx: dict, reference: dict, strict: bool) -> list[str]:
    qid = str(q.get("id") or "<missing-id>")
    errors: list[str] = []
    c = q.get("classification")
    if not isinstance(c, dict):
        return [f"{qid}: classification object is required"]

    if c.get("schema") != "physics-question-classification/v1":
        errors.append(f"{qid}: classification.schema must be physics-question-classification/v1")
    if strict and c.get("status") != "reviewed":
        errors.append(f"{qid}: classification.status must be reviewed")

    review = c.get("review")
    if not isinstance(review, dict):
        errors.append(f"{qid}: classification.review must be an object")
    elif strict:
        if review.get("reviewed") is not True:
            errors.append(f"{qid}: classification.review.reviewed must be true")
        if not _nonempty(review.get("method")):
            errors.append(f"{qid}: classification.review.method is required")

    cur = c.get("curriculum")
    if not isinstance(cur, dict):
        errors.append(f"{qid}: classification.curriculum must be an object")
        cur = {}
    course_id = str(cur.get("course_id") or "")
    if course_id != str(idx["course"].get("id") or ""):
        errors.append(f"{qid}: curriculum.course_id {course_id!r} does not match bank taxonomy")
    uid = str(cur.get("unit_id") or "")
    tid = str(cur.get("topic_id") or "")
    sids = [str(v) for v in (cur.get("subtopic_ids") or [])]
    if len(sids) != len(set(sids)):
        errors.append(f"{qid}: duplicate curriculum subtopic_ids")
    if uid not in idx["units"]:
        errors.append(f"{qid}: unknown curriculum unit_id {uid!r}")
    if tid not in idx["topics"]:
        errors.append(f"{qid}: unknown curriculum topic_id {tid!r}")
    elif idx["topics"][tid][0] != uid:
        errors.append(f"{qid}: topic {tid} does not belong to unit {uid}")
    for sid in sids:
        if sid not in idx["subtopics"]:
            errors.append(f"{qid}: unknown curriculum subtopic_id {sid!r}")
        else:
            suid, stid, _ = idx["subtopics"][sid]
            if suid != uid or stid != tid:
                errors.append(f"{qid}: subtopic {sid} does not belong to {uid}/{tid}")

    allowed_domains = {str(v.get("id")) for v in (reference.get("domains") or []) if isinstance(v, dict)}
    domain = str(c.get("physics_domain") or "")
    if domain not in allowed_domains:
        errors.append(f"{qid}: physics_domain {domain!r} is not in semantic-taxonomy.json")

    primary = c.get("primary_topic")
    if not isinstance(primary, dict) or not _nonempty(primary.get("name")) or not _nonempty(primary.get("evidence")):
        errors.append(f"{qid}: primary_topic requires name + evidence")

    seen_secondary = set()
    for i, item in enumerate(c.get("secondary_topics") or [], start=1):
        if not isinstance(item, dict) or not _nonempty(item.get("name")) or not _nonempty(item.get("evidence")):
            errors.append(f"{qid}: secondary_topics[{i}] requires name + evidence")
            continue
        key = str(item.get("name")).casefold()
        if key in seen_secondary:
            errors.append(f"{qid}: duplicate secondary topic {item.get('name')!r}")
        seen_secondary.add(key)

    kp = c.get("knowledge_points")
    if not isinstance(kp, list) or not kp:
        errors.append(f"{qid}: knowledge_points must be a non-empty array")
        kp = []
    seen_kp = set()
    for i, item in enumerate(kp, start=1):
        if not isinstance(item, dict):
            errors.append(f"{qid}: knowledge_points[{i}] must be an object")
            continue
        name = str(item.get("name") or "").strip()
        if not name or not _nonempty(item.get("evidence")):
            errors.append(f"{qid}: knowledge_points[{i}] requires name + evidence")
        if item.get("role") not in KNOWLEDGE_ROLES:
            errors.append(f"{qid}: knowledge_points[{i}].role must be one of {sorted(KNOWLEDGE_ROLES)}")
        if name.casefold() in seen_kp:
            errors.append(f"{qid}: duplicate knowledge point {name!r}")
        seen_kp.add(name.casefold())

    kinds = set(reference.get("solution_model_kinds") or [])
    models = c.get("solution_models")
    if not isinstance(models, list) or not models:
        errors.append(f"{qid}: solution_models must be a non-empty array")
        models = []
    primary_models = 0
    seen_models = set()
    for i, item in enumerate(models, start=1):
        if not isinstance(item, dict):
            errors.append(f"{qid}: solution_models[{i}] must be an object")
            continue
        name = str(item.get("name") or "").strip()
        if not name or not _nonempty(item.get("evidence")):
            errors.append(f"{qid}: solution_models[{i}] requires name + evidence")
        if item.get("kind") not in kinds:
            errors.append(f"{qid}: solution_models[{i}].kind {item.get('kind')!r} is invalid")
        if item.get("role") not in MODEL_ROLES:
            errors.append(f"{qid}: solution_models[{i}].role must be primary/secondary")
        elif item.get("role") == "primary":
            primary_models += 1
        if name.casefold() in seen_models:
            errors.append(f"{qid}: duplicate solution model {name!r}")
        seen_models.add(name.casefold())
    if models and primary_models < 1:
        errors.append(f"{qid}: at least one solution_model must have role=primary")

    allowed_skills = {str(v.get("id")) for v in (reference.get("skills") or []) if isinstance(v, dict)}
    skills = c.get("skills")
    if not isinstance(skills, list) or not skills:
        errors.append(f"{qid}: skills must be a non-empty array")
        skills = []
    seen_skills = set()
    for i, item in enumerate(skills, start=1):
        if not isinstance(item, dict):
            errors.append(f"{qid}: skills[{i}] must be an object")
            continue
        sid = str(item.get("id") or "")
        if sid not in allowed_skills:
            errors.append(f"{qid}: skills[{i}].id {sid!r} is not controlled vocabulary")
        if not _nonempty(item.get("evidence")):
            errors.append(f"{qid}: skills[{i}].evidence is required")
        if sid in seen_skills:
            errors.append(f"{qid}: duplicate skill {sid}")
        seen_skills.add(sid)

    difficulty = c.get("difficulty")
    errors.extend(f"{qid}: {error}" for error in DIFFICULTY.validate_difficulty(difficulty, strict=strict))

    confidence = c.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not (0 <= float(confidence) <= 1):
        errors.append(f"{qid}: confidence must be a number from 0 to 1")
    elif strict:
        threshold = float((reference.get("confidence") or {}).get("review_below", 0.75))
        if float(confidence) < threshold:
            errors.append(f"{qid}: confidence {confidence} is below review threshold {threshold}")

    if strict and c.get("derived_fields_version") != "1.0":
        errors.append(f"{qid}: run derive_semantic_tags.py; derived_fields_version must be 1.0")
    if strict:
        names = DERIVE.names_from_classification(c, {
            "course": idx["course"],
            "units": list(idx["units"].values()),
        })
        expected = {
            "course": names["course"],
            "unit": names["unit"],
            "topic": names["topic"],
            "subtopics": names["subtopics"],
            "knowledge_points": [str(v.get("name")) for v in kp if isinstance(v, dict) and v.get("name")],
            "solution_models": [str(v.get("name")) for v in models if isinstance(v, dict) and v.get("name")],
            "skills": [str(v.get("id")) for v in skills if isinstance(v, dict) and v.get("id")],
            "difficulty": DERIVE.difficulty_level(difficulty),
        }
        for field, value in expected.items():
            if q.get(field) != value:
                errors.append(f"{qid}: derived field {field} is stale; run derive_semantic_tags.py")
        expected_tags = set(DERIVE.derived_tags(q, {
            "course": idx["course"],
            "units": list(idx["units"].values()),
        }))
        actual_tags = {str(v) for v in (q.get("tags") or [])}
        missing = sorted(expected_tags - actual_tags)
        if missing:
            errors.append(f"{qid}: missing derived semantic tag(s): {', '.join(missing)}")
        generated_prefixes = tuple(DERIVE.GENERATED_PREFIXES)
        actual_generated = {tag for tag in actual_tags if tag.startswith(generated_prefixes)}
        unexpected = sorted(actual_generated - expected_tags)
        if unexpected:
            errors.append(f"{qid}: stale/unexpected derived semantic tag(s): {', '.join(unexpected)}")

    return errors


def validate(questions_data: dict, taxonomy: dict | None, reference: dict,
             strict: bool = True, knowledge_taxonomy: dict | None = None) -> dict:
    questions = questions_data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("questions.json must contain a top-level questions array")
    legacy = [q for q in questions if isinstance(q, dict) and (q.get("classification") or {}).get("schema") != KNOWLEDGE.SCHEMA]
    modern = [q for q in questions if isinstance(q, dict) and (q.get("classification") or {}).get("schema") == KNOWLEDGE.SCHEMA]
    errors = []
    if legacy:
        if not taxonomy:
            errors.append("v1 questions require --taxonomy (legacy bank taxonomy)")
        else:
            old_errors, idx = validate_taxonomy(taxonomy)
            errors.extend(old_errors)
            for q in legacy:
                errors.extend(validate_question(q, idx, reference, strict))
    if modern:
        if knowledge_taxonomy is None:
            errors.append("v2 questions require --knowledge-taxonomy from the pinned website source")
        else:
            for q in modern:
                errors.extend(KNOWLEDGE.validate_question(q, knowledge_taxonomy, strict))
    if len(legacy) + len(modern) != len(questions):
        errors.append("questions array contains a non-object entry")
    return {"status": "ok" if not errors else "error", "errors": errors,
            "question_count": len(questions), "v1_count": len(legacy), "v2_count": len(modern)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("questions", type=Path)
    p.add_argument("--taxonomy", type=Path, help="bank taxonomy for v1")
    p.add_argument("--knowledge-taxonomy", type=Path, help="pinned website taxonomy for v2")
    p.add_argument("--reference-taxonomy", type=Path, default=Path(__file__).parents[1] / "references" / "semantic-taxonomy.json")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    result = validate(
        json.loads(args.questions.read_text(encoding="utf-8")),
        json.loads(args.taxonomy.read_text(encoding="utf-8")) if args.taxonomy else None,
        json.loads(args.reference_taxonomy.read_text(encoding="utf-8")),
        strict=args.strict,
        knowledge_taxonomy=load_knowledge_taxonomy(args.knowledge_taxonomy) if args.knowledge_taxonomy else None,
    )
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for error in result["errors"]:
        print(f"ERROR: {error}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
