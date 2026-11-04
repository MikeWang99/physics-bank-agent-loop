"""Validate Pocket Cosmos TIMBAD audit records; publication requires APPROVED L1–L7.

This validates the record contract, not the correctness of a physics judgment.
"""
from __future__ import annotations

DIMENSIONS = set("TIMBAD")
REJECTION_CODES = {
    "FATAL_PHYSICS_ERROR", "UNDERDETERMINED", "AMBIGUOUS_UNFIXABLE",
    "OUT_OF_SCOPE", "DUPLICATE_NO_ADDED_VALUE", "MISLEADING_HARMFUL",
}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _strings(value, nonempty=False):
    return isinstance(value, list) and (bool(value) or not nonempty) and all(_text(v) for v in value)


def validate_difficulty(d, strict=True):
    errors = []
    if not isinstance(d, dict):
        return ["difficulty must be an object"]
    requires_drivers = ("rubric_id" not in d or d.get("review_status") == "APPROVED"
                        or (d.get("review_status") == "REVISE" and d.get("level") is not None))
    if not _strings(d.get("drivers"), nonempty=requires_drivers):
        errors.append("difficulty.drivers must be a string array (non-empty for a complete rating)")

    # Legacy records remain readable for migration, but may not silently acquire
    # new meanings just because their old numeric label is also between 1 and 7.
    if "rubric_id" not in d:
        if strict:
            errors.append("difficulty requires pocket-cosmos-timbad reassessment before strict publication")
        if type(d.get("level")) is not int or d["level"] not in range(1, 6):
            errors.append("legacy difficulty.level must be an integer 1-5")
        return errors

    if d.get("rubric_id") != "pocket-cosmos-timbad" or d.get("rubric_version") != "1.0":
        errors.append("difficulty requires rubric_id=pocket-cosmos-timbad and rubric_version=1.0")
    status = d.get("review_status")
    level = d.get("level")
    if status not in ("APPROVED", "REVISE", "NEEDS_REVIEW", "REJECTED"):
        errors.append("difficulty.review_status is invalid")
    if "level" not in d or (level is not None and (type(level) is not int or level not in range(0, 8))):
        errors.append("difficulty.level must be an integer 0-7 or null")
    expected_label = f"L{level}" if type(level) is int and level in range(0, 8) else None
    if "overall_level" not in d or d.get("overall_level") != expected_label:
        errors.append("difficulty.overall_level must agree with level (L0–L7/null)")
    if (level == 0) != (status == "REJECTED"):
        errors.append("difficulty L0 is reserved for REJECTED, and REJECTED requires L0")
    if status == "NEEDS_REVIEW" and level is not None:
        errors.append("difficulty NEEDS_REVIEW requires level=null")
    if status == "APPROVED" and (type(level) is not int or level not in range(1, 8)):
        errors.append("difficulty APPROVED requires L1–L7")
    if status == "REJECTED" and d.get("rejection_reason") not in tuple(REJECTION_CODES):
        errors.append("difficulty REJECTED requires a controlled rejection_reason")
    if status != "REJECTED" and d.get("rejection_reason") is not None:
        errors.append("difficulty rejection_reason must be null unless REJECTED")
    if status != "APPROVED" and not _text(d.get("review_notes")):
        errors.append("difficulty non-approved record requires review_notes")
    if not _strings(d.get("question_quality_flags")):
        errors.append("difficulty.question_quality_flags must be a string array")

    complete = status == "APPROVED" or (status == "REVISE" and level is not None)
    timbad = d.get("timbad")
    if not isinstance(timbad, dict) or set(timbad) != DIMENSIONS:
        errors.append("difficulty.timbad must contain exactly T/I/M/B/A/D")
    else:
        for key, item in timbad.items():
            if not isinstance(item, dict):
                errors.append(f"difficulty.timbad.{key} must be an object")
                continue
            score = item.get("score")
            if not (type(score) is int and score in {0, 1, 2}) and not (score is None and not complete):
                errors.append(f"difficulty.timbad.{key}.score must be integer 0/1/2 (null only for incomplete/rejected audits)")
            if complete or score is not None:
                for field in ("rationale", "evidence"):
                    if not _text(item.get(field)):
                        errors.append(f"difficulty.timbad.{key}.{field} is required")

    for field in ("primary_bottleneck", "secondary_bottleneck"):
        if d.get(field) not in tuple(DIMENSIONS | {"NONE"}):
            errors.append(f"difficulty.{field} must be T/I/M/B/A/D/NONE")
    if d.get("primary_bottleneck") in tuple(DIMENSIONS) and d.get("primary_bottleneck") == d.get("secondary_bottleneck"):
        errors.append("difficulty bottlenecks must be distinct unless NONE")
    if d.get("insight_depth") not in ("NONE", "MODEST", "SUBSTANTIAL", "DEEP", "EXCEPTIONAL"):
        errors.append("difficulty.insight_depth is invalid")
    for field in ("key_insights", "prerequisites", "math_tools", "key_skills", "solution_outline"):
        if not _strings(d.get(field), nonempty=(field == "solution_outline" and complete)):
            errors.append(f"difficulty.{field} must be a string array" + (" with a reliable outline" if field == "solution_outline" and complete else ""))
    if complete:
        for field in ("overall_reason", "boundary_reason", "topic", "subtopic", "final_answer"):
            if not _text(d.get(field)):
                errors.append(f"difficulty.{field} is required for a complete rating")
        if type(level) is int and level >= 5 and (not d.get("key_insights") or d.get("insight_depth") in (None, "NONE")):
            errors.append("difficulty L5–L7 requires a substantive key_insight and insight_depth")
    if d.get("rating_confidence") not in ("HIGH", "MEDIUM", "LOW"):
        errors.append("difficulty.rating_confidence must be HIGH/MEDIUM/LOW")
    if type(d.get("needs_human_review")) is not bool:
        errors.append("difficulty.needs_human_review must be boolean")
    if d.get("rating_confidence") == "LOW" and d.get("needs_human_review") is not True:
        errors.append("difficulty LOW confidence requires needs_human_review=true")
    if status == "NEEDS_REVIEW" and d.get("needs_human_review") is not True:
        errors.append("difficulty NEEDS_REVIEW requires needs_human_review=true")
    if strict and (status != "APPROVED" or d.get("needs_human_review") is not False or d.get("rating_confidence") == "LOW"):
        errors.append("difficulty strict publication requires APPROVED with no pending human review")
    return errors
