#!/usr/bin/env python3
"""Compile a validated physics-bank bundle into a Pocket Cosmos publish bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_BANK_SCRIPT_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(_BANK_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_BANK_SCRIPT_DIR))
from knowledge_taxonomy import load_knowledge_taxonomy
from validate_knowledge_classification import validate_question as validate_knowledge_question

SCHEMA = "pocket-cosmos-publish-bundle/v1"
PUBLISHER_VERSION = "1.2.0"
ALLOWED_SYSTEMS = {
    "ap-physics-1", "ap-physics-2", "ap-c-mech", "ap-c-em",
    "igcse", "competition", "bpho", "a-level", "physics-bowl",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value) -> str:
    return hashlib.sha256(compact(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def unique_strings(values):
    seen = set()
    out = []
    for value in values:
        text = str(value or "").strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(text)
    return out


def full_prompt(question: dict) -> str:
    context = str(question.get("context") or "").strip()
    stem = str(question.get("stem") or "").strip()
    return "\n\n".join(part for part in (context, stem) if part)


def source_ref(question: dict, config: dict) -> str:
    explicit = str(question.get("source_ref") or "").strip()
    if explicit:
        return explicit
    src = question.get("source") if isinstance(question.get("source"), dict) else {}
    parts = []
    label = str((config.get("practice_set") or {}).get("source_label") or "").strip()
    if label:
        parts.append(label)
    source_file = str(src.get("file") or src.get("document") or "").strip()
    if source_file:
        parts.append(Path(source_file).name)
    original = question.get("original_number")
    if original is None:
        original = (src or {}).get("original_number")
    if original not in (None, ""):
        parts.append(f"Q{original}")
    pages = question.get("source_pages") or []
    if pages:
        parts.append("source page(s) " + ", ".join(str(v) for v in pages))
    return " · ".join(parts) or str((config.get("practice_set") or {}).get("title") or "Physics question bank")


def layout_compatibility(question: dict, asset_index: dict) -> dict:
    top_ids = [str(v) for v in (question.get("asset_ids") or [])]
    narrative_ids = [
        aid for aid in top_ids
        if isinstance(asset_index.get(aid), dict)
        and asset_index[aid].get("role") in {"stem", "shared"}
    ]
    if not narrative_ids:
        return {"status": "native", "reason": "no narrative figures", "figureOrder": []}

    blocks = question.get("layout_blocks")
    if not isinstance(blocks, list) or not blocks:
        return {
            "status": "unsupported",
            "reason": "stem/shared figures exist but layout_blocks are missing",
            "figureOrder": narrative_ids,
        }

    figure_order = []
    first_figure_seen = False
    text_after_figure = False
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type") or "").strip().lower()
        if kind == "figure":
            aid = str(block.get("asset_id") or "")
            if aid:
                figure_order.append(aid)
            first_figure_seen = True
        elif kind == "text" and str(block.get("text") or "").strip():
            if first_figure_seen:
                text_after_figure = True

    if set(figure_order) != set(narrative_ids) or len(figure_order) != len(narrative_ids):
        return {
            "status": "unsupported",
            "reason": "layout figure coverage does not match stem/shared assets",
            "figureOrder": figure_order or narrative_ids,
        }

    if text_after_figure:
        return {
            "status": "degraded",
            "reason": "current Practice UI renders all prompt text before all narrative figures",
            "figureOrder": figure_order,
        }

    return {
        "status": "native",
        "reason": "all narrative text precedes narrative figures",
        "figureOrder": figure_order,
    }


def answer_render_compatibility(question: dict) -> dict:
    """Current Practice UI supports at most one fixed-position solutionImage."""
    answer = question.get("answer") if isinstance(question.get("answer"), dict) else {}
    aids = [str(v) for v in (answer.get("asset_ids") or [])]
    blocks = answer.get("layout_blocks") or []
    text_after_figure = False
    seen_figure = False
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type") or ("figure" if "asset_id" in block else "text"))
        if kind == "figure":
            seen_figure = True
        elif kind == "text" and str(block.get("text") or "").strip() and seen_figure:
            text_after_figure = True
    if len(aids) > 1 or text_after_figure:
        return {
            "status": "degraded",
            "reason": "current Practice UI can render only one trailing solutionImage, not ordered answer.layout_blocks",
        }
    return {"status": "native", "reason": "answer can be shown as text and at most one trailing image"}


def readable_tags(question: dict) -> list[str]:
    c = question.get("classification") if isinstance(question.get("classification"), dict) else {}
    primary = c.get("primary_topic") if isinstance(c.get("primary_topic"), dict) else {}
    difficulty = question.get("difficulty")
    values = [
        primary.get("name"),
        question.get("topic"),
        *(question.get("subtopics") or []),
    ]
    if isinstance(difficulty, int):
        values.append(f"Difficulty {difficulty}")
    values.extend(question.get("tags") or [])
    return unique_strings(values)


def specialty_tags(question: dict) -> list[str]:
    c = question.get("classification") if isinstance(question.get("classification"), dict) else {}
    primary = c.get("primary_topic") if isinstance(c.get("primary_topic"), dict) else {}
    secondaries = [
        item.get("name") for item in (c.get("secondary_topics") or [])
        if isinstance(item, dict)
    ]
    return unique_strings([
        primary.get("name"),
        *(question.get("subtopics") or []),
        *secondaries,
    ])


def answer_labels(question: dict) -> list[str]:
    source = question.get("answer") if isinstance(question.get("answer"), dict) else {}
    raw_label = str(source.get("label") or "").strip()
    legacy_labels = [part.upper() for part in re.split(r"[,;\s/]+", raw_label) if part]
    explicit = source.get("correct_labels")
    has_explicit = explicit is not None
    if has_explicit and not isinstance(explicit, list):
        raise ValueError("answer.correct_labels must be an array of choice labels")
    if has_explicit:
        labels = [item.strip().upper() if isinstance(item, str) else "" for item in explicit]
        if any(not item for item in labels):
            raise ValueError("answer.correct_labels contains a blank or non-string label")
    else:
        labels = legacy_labels
    if has_explicit and legacy_labels and sorted(labels) != sorted(legacy_labels):
        raise ValueError("answer.label conflicts with answer.correct_labels")
    if len(set(labels)) != len(labels):
        raise ValueError("answer contains duplicate correct choice labels")
    choices = question.get("choices") if isinstance(question.get("choices"), list) else []
    choice_labels = {str(choice.get("label") or "").strip().upper() for choice in choices if isinstance(choice, dict)}
    if has_explicit and labels and not choice_labels:
        raise ValueError("answer.correct_labels requires answer choices")
    if labels and choice_labels and any(label not in choice_labels for label in labels):
        raise ValueError("answer contains a label that does not belong to a choice")
    return labels


def answer_payload(question: dict, mode: str, config: dict) -> tuple[dict, dict]:
    source = question.get("answer") if isinstance(question.get("answer"), dict) else {}
    labels = answer_labels(question)
    label = ",".join(labels) or None
    text = str(source.get("text") or "").strip() or None
    evidence = str(source.get("evidence") or "").strip() or "not-provided"

    answer = {
        "correctAnswer": label,
        "solution": text,
        "criteria": source.get("criteria") if isinstance(source.get("criteria"), list) else [],
        "sampleAnswer": source.get("sampleAnswer"),
        "evidence": evidence,
    }
    step = {
        "criteria": answer["criteria"],
        "maxScore": 1 if (mode == "multiple_choice" and label) else 0,
    }
    if label:
        step["correctAnswer"] = label
    if text:
        step["solution"] = text
    # A source key containing only A/B/C/D is not a worked solution.
    # Do NOT invent "Official answer: A." for student-facing display.
    else:
        nudge = str((config.get("answers") or {}).get("missing_mcq_nudge") or "").strip()
        if mode == "multiple_choice" and nudge:
            step["answerNudge"] = nudge
    return answer, step


def asset_descriptor(bank_root: Path, asset: dict, practice_set_id: str, storage: dict) -> dict:
    rel = str(asset.get("file") or "")
    local = (bank_root / rel).resolve()
    if not local.is_file():
        raise ValueError(f"asset file not found: {rel}")
    sha = file_hash(local)
    suffix = local.suffix.lower()
    extensions = {
        ".png": ("image/png", ".png"),
        ".jpg": ("image/jpeg", ".jpg"),
        ".jpeg": ("image/jpeg", ".jpg"),
        ".webp": ("image/webp", ".webp"),
    }
    if suffix not in extensions:
        raise ValueError(f"unsupported runtime image type: {rel}")
    content_type, suffix = extensions[suffix]
    prefix = str(storage.get("prefix") or "banks/production/assets").strip("/")
    if prefix == "banks":
        prefix = "banks/production/assets"
    if prefix != "banks/production/assets":
        raise ValueError("production API publishing requires storage.prefix=banks/production/assets")
    bucket = str(storage.get("bucket") or "question-assets")
    if bucket != "question-assets":
        raise ValueError("production API publishing requires the question-assets bucket")
    aid = str(asset.get("id") or "")
    safe_aid = re.sub(r"[^a-z0-9]+", "-", aid.lower()).strip("-")
    if not safe_aid:
        raise ValueError(f"asset ID has no safe characters: {aid!r}")
    storage_path = f"{prefix}/{practice_set_id}/{safe_aid}-{sha[:12]}{suffix}"
    return {
        "physicsBankAssetId": aid,
        "localFile": rel,
        "sha256": sha,
        "size": local.stat().st_size,
        "contentType": content_type,
        "storageBucket": bucket,
        "storagePath": storage_path,
        "sourceRole": asset.get("role"),
        "source": asset.get("source") or {},
        "review": asset.get("review") or {},
    }


def compile_bank(bank_root: Path, config: dict) -> dict:
    questions_data = load_json(bank_root / "questions.json")
    assets_data = load_json(bank_root / "assets.json")
    v1_taxonomy_path = bank_root / "classification-taxonomy.json"
    taxonomy = load_json(v1_taxonomy_path) if v1_taxonomy_path.is_file() else {}
    knowledge_taxonomy_path = bank_root / "knowledge-taxonomy.json"
    knowledge_taxonomy = None
    questions = questions_data.get("questions")
    assets = assets_data.get("assets")
    if not isinstance(questions, list):
        raise ValueError("questions.json must contain questions[]")
    if not isinstance(assets, list):
        raise ValueError("assets.json must contain assets[]")
    v2_present = any(isinstance(q, dict) and (q.get("classification") or {}).get("schema") == "physics-question-classification/v2" for q in questions)
    if v2_present:
        if not knowledge_taxonomy_path.is_file():
            raise ValueError("v2 publication requires a pinned knowledge-taxonomy.json in the bank root")
        knowledge_taxonomy = load_knowledge_taxonomy(knowledge_taxonomy_path)
    if any((q.get("classification") or {}).get("schema") != "physics-question-classification/v2" for q in questions) and not taxonomy:
        raise ValueError("v1 publishing requires classification-taxonomy.json")

    ps = config.get("practice_set")
    if not isinstance(ps, dict):
        raise ValueError("config.practice_set is required")
    practice_set_id = str(ps.get("id") or "").strip()
    if not practice_set_id:
        raise ValueError("config.practice_set.id is required")
    system = str(ps.get("system") or "").strip()
    if system not in ALLOWED_SYSTEMS:
        raise ValueError(f"unsupported practice_set.system: {system!r}")
    practice_kind = str(ps.get("practice_kind") or "").strip()
    if practice_kind not in {"mcq", "structured"}:
        raise ValueError("practice_set.practice_kind must be mcq or structured")

    storage = config.get("storage") if isinstance(config.get("storage"), dict) else {}
    rendering = config.get("rendering") if isinstance(config.get("rendering"), dict) else {}
    allow_degraded = rendering.get("allow_layout_degradation") is True
    asset_index = {str(a.get("id")): a for a in assets if isinstance(a, dict) and a.get("id")}
    asset_cache = {
        aid: asset_descriptor(bank_root, asset, practice_set_id, storage)
        for aid, asset in asset_index.items()
    }

    compiled = []
    for position, q in enumerate(questions):
        if not isinstance(q, dict):
            raise ValueError(f"question at position {position} is not an object")
        qid = str(q.get("id") or "").strip()
        if not qid:
            raise ValueError(f"question at position {position} has no id")
        classification = q.get("classification") or {}
        is_v2 = classification.get("schema") == "physics-question-classification/v2"
        if is_v2:
            issues = validate_knowledge_question(q, knowledge_taxonomy, strict=True)
            if issues:
                raise ValueError(f"{qid}: v2 strict classification invalid: {'; '.join(issues)}")
            if q["source_system"] != system:
                raise ValueError(f"{qid}: source_system {q['source_system']} differs from practice_set.system {system}; use a matching source collection")
        choices = q.get("choices") if isinstance(q.get("choices"), list) else []
        mode = "multiple_choice" if choices else "structured"
        prompt = full_prompt(q)
        if not prompt:
            raise ValueError(f"{qid}: empty prompt")

        compat = layout_compatibility(q, asset_index)
        if compat["status"] == "unsupported":
            raise ValueError(f"{qid}: {compat['reason']}")
        if compat["status"] == "degraded" and not allow_degraded:
            raise ValueError(
                f"{qid}: web layout would be degraded: {compat['reason']}; "
                "set rendering.allow_layout_degradation=true only with explicit acceptance"
            )

        answer_compat = answer_render_compatibility(q)
        if answer_compat["status"] == "degraded" and rendering.get("allow_answer_layout_degradation") is not True:
            raise ValueError(
                f"{qid}: answer render would be degraded: {answer_compat['reason']}; "
                "upgrade the site solution renderer or explicitly allow answer layout degradation"
            )

        source = source_ref(q, config)
        answer, answer_step = answer_payload(q, mode, config)
        step = {
            "id": qid,
            "mode": mode,
            "tags": readable_tags(q),
            "title": f"Question {position + 1}",
            "prompt": prompt,
            "source": source,
            "choices": [
                {"label": str(ch.get("label") or ""), "text": str(ch.get("text") or "")}
                for ch in choices if isinstance(ch, dict)
            ],
            "context": str(q.get("context") or ""),
            "difficulty": (classification["difficulty"]["level"] if is_v2 else q.get("difficulty")),
            "specialtyTags": specialty_tags(q) if system == "competition" and not is_v2 else [],
            **({"primaryKnowledgeUid": classification["primary_knowledge_uid"], "sourceSystem": q["source_system"]} if is_v2 else {}),
            "choiceLayout": str(rendering.get("choice_layout") or "stacked"),
            **answer_step,
        }
        # Remove null optional values from runtime mapping.
        step = {k: v for k, v in step.items() if v is not None}

        physics_bank_meta = {
            "schema": "physics-bank-web-publish/v1",
            "publisherVersion": PUBLISHER_VERSION,
            "questionId": qid,
            "bankSchemaVersion": questions_data.get("schema_version"),
            "classification": q.get("classification"),
            **({"primaryKnowledgeUid": classification["primary_knowledge_uid"],
                "sourceSystem": q["source_system"],
                "sourceEvent": q.get("source_event"),
                "knowledgeTaxonomy": {"version": knowledge_taxonomy["version"], "sha256": knowledge_taxonomy["sha256"]}} if is_v2 else {}),
            "layoutBlocks": q.get("layout_blocks") or [],
            "layoutReview": q.get("layout_review"),
            "sourcePages": q.get("source_pages") or [],
            "source": q.get("source") or {},
            "extraction": q.get("extraction") or {},
            "assetIds": q.get("asset_ids") or [],
            "semanticTags": q.get("tags") or [],
            "taxonomyCourse": taxonomy.get("course") or {},
            "renderCompatibility": compat,
            "answer": q.get("answer") or {},
            "answerRenderCompatibility": answer_compat,
        }

        count = len(questions)
        subtitle = str(ps.get("subtitle") or "").strip()
        if not subtitle:
            label = "Multiple Choice" if practice_kind == "mcq" else "Structured Questions"
            subtitle = f"{label} · {count} questions"
        practice_set = {
            "id": practice_set_id,
            "category": ps.get("category"),
            "label": ps.get("label"),
            "system": system,
            "practiceKind": practice_kind,
            "chapter": ps.get("chapter"),
            "chapterTitle": ps.get("chapter_title"),
            "title": ps.get("title"),
            "subtitle": subtitle,
            "eyebrow": ps.get("eyebrow"),
            "description": ps.get("description"),
            "sources": ps.get("sources") or [],
        }
        practice_set = {k: v for k, v in practice_set.items() if v not in (None, "")}

        metadata = {
            "formatVersion": 2,
            "practiceSet": practice_set,
            "practiceStep": step,
            "physicsBank": physics_bank_meta,
        }

        q_asset_ids = [str(v) for v in (q.get("asset_ids") or [])]
        choice_counts = {}
        for aid in q_asset_ids:
            a = asset_index.get(aid)
            if a and a.get("role") == "choice":
                label = str(a.get("choice_label") or "")
                choice_counts[label] = choice_counts.get(label, 0) + 1

        db_assets = []
        narrative_order = compat.get("figureOrder") or []
        for order, aid in enumerate(narrative_order):
            a = asset_index.get(aid)
            if not a:
                raise ValueError(f"{qid}: unknown narrative asset {aid}")
            base = dict(asset_cache[aid])
            is_first = order == 0
            base.update({
                "role": "stem" if is_first else "figure",
                "choiceKey": None,
                "sortOrder": order if not is_first else 0,
                "metadata": {
                    "slot": "image" if is_first else "supportingImages",
                    "physicsBankAssetId": aid,
                    "physicsBankRole": a.get("role"),
                    "alt": f"{ps.get('title') or practice_set_id} figure for Question {position + 1}",
                    "downloadName": Path(str(a.get("file") or aid)).name,
                    "source": a.get("source") or {},
                },
            })
            db_assets.append(base)

        for aid in q_asset_ids:
            a = asset_index.get(aid)
            if not a or a.get("role") != "choice":
                continue
            label = str(a.get("choice_label") or "")
            index = int(a.get("choice_index") or 1)
            base = dict(asset_cache[aid])
            base.update({
                "role": "choice",
                "choiceKey": label,
                "sortOrder": max(0, index - 1),
                "metadata": {
                    "slot": "choices.images" if choice_counts.get(label, 0) > 1 else "choices.image",
                    "physicsBankAssetId": aid,
                    "physicsBankRole": "choice",
                    "alt": f"Option {label} image",
                    "downloadName": Path(str(a.get("file") or aid)).name,
                    "source": a.get("source") or {},
                },
            })
            db_assets.append(base)

        # Answer diagrams are distinct from stem and choice media. Preserve
        # every answer image as an immutable version-bound asset.
        answer_data = q.get("answer") if isinstance(q.get("answer"), dict) else {}
        for order, aid in enumerate(answer_data.get("asset_ids") or []):
            asset = asset_index.get(str(aid))
            if not asset or asset.get("role") != "answer":
                raise ValueError(f"{qid}: answer references missing/non-answer asset {aid}")
            base = dict(asset_cache[str(aid)])
            base.update({
                "role": "answer",
                "choiceKey": None,
                "sortOrder": order,
                "metadata": {
                    "slot": "solutionImage" if order == 0 else "answerAssets",
                    "physicsBankAssetId": str(aid),
                    "physicsBankRole": "answer",
                    "alt": f"Worked solution figure for Question {position + 1}",
                    "downloadName": Path(str(asset.get("file") or aid)).name,
                    "source": asset.get("source") or {},
                },
            })
            db_assets.append(base)

        hash_basis = {
            "stem": prompt,
            "choices": step["choices"],
            "answer": answer,
            "metadata": metadata,
            "sourceYear": q.get("year"),
            "sourceRef": source,
            "assets": [
                {
                    "id": a["physicsBankAssetId"],
                    "sha256": a["sha256"],
                    "role": a["role"],
                    "choiceKey": a["choiceKey"],
                    "sortOrder": a["sortOrder"],
                    "storagePath": a["storagePath"],
                    "metadata": a["metadata"],
                }
                for a in db_assets
            ],
        }
        digest = content_hash(hash_basis)
        compiled.append({
            "question": {
                "id": f"{practice_set_id}::{qid}",
                "practiceSetId": practice_set_id,
                "legacyQuestionId": qid,
                "status": "active",
                "position": position,
            },
            "version": {
                "stem": prompt,
                "choices": step["choices"],
                "answer": answer,
                "explanation": None,
                "metadata": metadata,
                "sourceYear": q.get("year"),
                "sourceRef": source,
                "contentHash": digest,
            },
            "assets": db_assets,
            "renderCompatibility": compat,
        })

    return {
        "schema": SCHEMA,
        "publisherVersion": PUBLISHER_VERSION,
        "practiceSet": compiled[0]["version"]["metadata"]["practiceSet"] if compiled else {
            "id": practice_set_id, "system": system, "practiceKind": practice_kind
        },
        "sourceBank": {
            "schemaVersion": questions_data.get("schema_version"),
            "taxonomySchema": taxonomy.get("schema") or ("pocket-cosmos-unified-knowledge/v1" if v2_present else None),
            **({"knowledgeTaxonomySha256": knowledge_taxonomy["sha256"]} if v2_present else {}),
            "questionCount": len(questions),
        },
        "questions": compiled,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bank_root", type=Path)
    p.add_argument("config", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    config = load_json(args.config)
    if config.get("schema") != "pocket-cosmos-publish-config/v1":
        raise SystemExit("config schema must be pocket-cosmos-publish-config/v1")
    bundle = compile_bank(args.bank_root.resolve(), config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Compiled {len(bundle['questions'])} question(s) for {bundle['practiceSet'].get('id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
