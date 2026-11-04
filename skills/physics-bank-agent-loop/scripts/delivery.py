#!/usr/bin/env python3
"""Add reviewed student answers and publish independently compilable questions.

This is deliberately POST-acceptance. It never edits the source PhysicsBank
questions.json, original image files, source proofs, or Creator/Reviewer loop.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "physics-bank" / "skills" / "physics-bank-web-publisher" / "scripts"
ANSWERS_SCHEMA = "physics-bank-delivery-answers/v1"
BUNDLE_SCHEMA = "pocket-cosmos-publish-bundle/v1"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path}")
    return value


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def recalculate_hash(item: dict) -> None:
    version = item["version"]
    basis = {
        "stem": version["stem"],
        "choices": version["choices"],
        "answer": version["answer"],
        "metadata": version["metadata"],
        "sourceYear": version.get("sourceYear"),
        "sourceRef": version.get("sourceRef"),
        "assets": [
            {
                "id": a["physicsBankAssetId"],
                "sha256": a["sha256"],
                "role": a["role"],
                "choiceKey": a.get("choiceKey"),
                "sortOrder": a["sortOrder"],
                "storagePath": a["storagePath"],
                "metadata": a["metadata"],
            }
            for a in item.get("assets", [])
        ],
    }
    version["contentHash"] = digest(basis)


def markdown_latex(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must contain non-empty Markdown + LaTeX")
    result = value.strip()
    if any(token in result for token in (r"\(", r"\)", r"\[", r"\]")):
        raise ValueError(f"{field}: use $...$ or $$...$$, not backslash math delimiters")
    if len(re.findall(r"(?<!\\)\$", result)) % 2:
        raise ValueError(f"{field}: unbalanced LaTeX dollar delimiters")
    if re.search(r"<[a-zA-Z][^>]*>", result):
        raise ValueError(f"{field}: HTML is not permitted")
    return result


def reviewed_answer(source: dict, question: dict) -> dict:
    qid = str(question.get("id") or "")
    kind = "mcq" if question.get("choices") else "frq"
    if source.get("kind") != kind:
        raise ValueError(f"{qid}: answer kind must be {kind}")
    creator = source.get("creator")
    reviewer = source.get("reviewer")
    if not isinstance(creator, dict) or not isinstance(reviewer, dict):
        raise ValueError(f"{qid}: answer needs separate creator and reviewer evidence")
    creator_id, reviewer_id = str(creator.get("id") or "").strip(), str(reviewer.get("id") or "").strip()
    if not creator_id or not reviewer_id or creator_id == reviewer_id:
        raise ValueError(f"{qid}: creator and independent reviewer identities must differ")
    if reviewer.get("independent") is not True or reviewer.get("verdict") != "ACCEPT":
        raise ValueError(f"{qid}: independent answer review has not passed")
    if not str(reviewer.get("notes") or "").strip():
        raise ValueError(f"{qid}: reviewer must include verification notes")
    explanation = markdown_latex(source.get("detailed_explanation"), f"{qid}.detailed_explanation")
    if kind == "mcq":
        labels = source.get("correct_labels")
        if not isinstance(labels, list) or not labels or any(not isinstance(x, str) for x in labels):
            raise ValueError(f"{qid}: correct_labels must be a nonempty list")
        labels = [x.strip().upper() for x in labels]
        if len(set(labels)) != len(labels):
            raise ValueError(f"{qid}: duplicate answer labels")
        legal = {str(c.get("label") or "").strip().upper() for c in question["choices"]}
        if not set(labels) <= legal:
            raise ValueError(f"{qid}: answer label not among the choices")
        source_answer = question.get("answer") or {}
        official = [x.upper() for x in re.split(r"[,;/\s]+", str(source_answer.get("label") or "").strip()) if x]
        if official and set(official) != set(labels):
            raise ValueError(f"{qid}: AI answer conflicts with supplied source key")
        return {
            "kind": kind,
            "label": ",".join(labels),
            "text": "**Correct answer: " + ", ".join(labels) + "**\n\n**Detailed explanation**\n\n" + explanation,
            "examAnswer": None,
            "creatorId": creator_id,
            "reviewerId": reviewer_id,
            "reviewNotes": reviewer["notes"].strip(),
            "origin": "ai_generated" if not (source_answer.get("text") or official) else "ai_enhanced",
        }
    exam = markdown_latex(source.get("exam_answer"), f"{qid}.exam_answer")
    return {
        "kind": kind,
        "label": None,
        "text": "**Exam-style answer**\n\n" + exam + "\n\n**Detailed explanation**\n\n" + explanation,
        "examAnswer": exam,
        "detailedExplanation": "**Detailed explanation**\n\n" + explanation,
        "creatorId": creator_id,
        "reviewerId": reviewer_id,
        "reviewNotes": reviewer["notes"].strip(),
        "origin": "ai_generated" if not (question.get("answer") or {}).get("text") else "ai_enhanced",
    }


def import_compiler():
    filename = SCRIPT_DIR / "compile_publish_bundle.py"
    if not filename.is_file():
        raise RuntimeError(f"Bundled PhysicsBank publisher not found: {filename}")
    spec = importlib.util.spec_from_file_location("physics_bank_delivery_compiler", filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def question_assets(question: dict) -> set[str]:
    asset_ids = {str(a) for a in (question.get("asset_ids") or [])}
    for choice in question.get("choices") or []:
        asset_ids.update(str(x) for x in (choice.get("asset_ids") or []))
    asset_ids.update(str(x) for x in ((question.get("answer") or {}).get("asset_ids") or []))
    for block in question.get("layout_blocks") or []:
        if block.get("asset_id"):
            asset_ids.add(str(block["asset_id"]))
    return asset_ids


def isolated_compile(bank: Path, config: dict, question: dict, position: int, assets: list, compiler) -> dict:
    needed = question_assets(question)
    selected = [a for a in assets if str(a.get("id")) in needed]
    if len(selected) != len(needed):
        raise ValueError("missing asset definitions: " + ", ".join(sorted(needed - {str(a.get("id")) for a in selected})))
    with tempfile.TemporaryDirectory(prefix="physics-bank-delivery-") as tmp:
        root = Path(tmp)
        original = load(bank / "questions.json")
        original["questions"] = [question]
        dump(root / "questions.json", original)
        manifest = load(bank / "assets.json")
        manifest["assets"] = selected
        dump(root / "assets.json", manifest)
        for taxonomy in ("knowledge-taxonomy.json", "classification-taxonomy.json"):
            if (bank / taxonomy).is_file():
                shutil.copy2(bank / taxonomy, root / taxonomy)
        for asset in selected:
            relative = Path(str(asset["file"]))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe asset path {relative}")
            dest = root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bank / relative, dest)
        result = compiler.compile_bank(root, config)
        item = result["questions"][0]
        item["question"]["position"] = position
        item["version"]["metadata"]["practiceStep"]["title"] = f"Question {position + 1}"
        recalculate_hash(item)
        return item


def run(bank: Path, config_file: Path, answers_file: Path, output_dir: Path, apply: bool) -> dict:
    bank, output_dir = bank.resolve(), output_dir.resolve()
    questions = load(bank / "questions.json").get("questions")
    assets = load(bank / "assets.json").get("assets")
    config = load(config_file)
    answers = load(answers_file)
    if not isinstance(questions, list) or not isinstance(assets, list):
        raise ValueError("Invalid canonical bank questions/assets array")
    if config.get("schema") != "pocket-cosmos-publish-config/v1":
        raise ValueError("Invalid publisher config")
    if answers.get("schema") != ANSWERS_SCHEMA or not isinstance(answers.get("questions"), list):
        raise ValueError("Invalid delivery answer file schema")
    indexed = {}
    for entry in answers["questions"]:
        key = str(entry.get("id") or "")
        if not key or key in indexed:
            raise ValueError(f"Missing/duplicate answer entry ID: {key}")
        indexed[key] = entry
    original_ids = [str(q.get("id") or "") for q in questions]
    if not all(original_ids) or len(set(original_ids)) != len(original_ids):
        raise ValueError("Canonical bank contains missing/duplicate IDs")
    if set(indexed) - set(original_ids):
        raise ValueError("Delivery answers contain unknown question IDs")

    # Freeze set metadata so one-question compilation yields the same set identity
    # and catalog label as whole-bank compilation.
    config = copy.deepcopy(config)
    ps = config.setdefault("practice_set", {})
    if not ps.get("subtitle"):
        label = "Multiple Choice" if ps.get("practice_kind") == "mcq" else "Structured Questions"
        ps["subtitle"] = f"{label} · {len(questions)} questions"
    compiler = import_compiler()
    ready, priority, normal = [], [], []
    for pos, question in enumerate(questions):
        qid = original_ids[pos]
        try:
            if qid not in indexed:
                raise ValueError("missing independently verified standardized answer")
            answer = reviewed_answer(indexed[qid], question)
            item = isolated_compile(bank, config, question, pos, assets, compiler)
            version = item["version"]
            meta = version["metadata"]
            step = meta["practiceStep"]
            preserved = version["answer"]
            # MCQ shows one labeled answer+explanation; FRQ uses two distinct
            # existing Practice disclosures, avoiding a duplicated exam answer.
            student_solution = answer.get("detailedExplanation") or answer["text"]
            preserved["solution"] = student_solution
            if answer["label"]:
                preserved["correctAnswer"] = answer["label"]
                step["correctAnswer"] = answer["label"]
                step["maxScore"] = 1
            if answer["examAnswer"]:
                preserved["sampleAnswer"] = answer["examAnswer"]
                step["sampleAnswer"] = answer["examAnswer"]
            step["solution"] = student_solution
            meta["physicsBank"]["deliveryAnswer"] = {
                "schema": ANSWERS_SCHEMA,
                "origin": answer["origin"],
                "creatorId": answer["creatorId"],
                "reviewerId": answer["reviewerId"],
                "independentReview": "ACCEPT",
                "reviewNotes": answer["reviewNotes"],
                "format": "markdown+latex",
                "kind": answer["kind"],
            }
            recalculate_hash(item)
            ready.append(item)
            normal.append({"questionId": qid, "reason": "published_pending_human_review", "priority": "normal"})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            priority.append({"questionId": qid, "position": pos, "priority": "high",
                             "status": "not_published", "reason": str(exc)})
    report = {
        "schema": "physics-bank-delivery-report/v1",
        "sourceQuestionCount": len(questions),
        "readyCount": len(ready),
        "highPriorityCount": len(priority),
        "normalReviewCount": len(normal),
        "highPriorityReview": priority,
        "normalHumanReview": normal,
        "published": False,
    }
    bundle_file = output_dir / "web-publish-ready.json"
    if ready:
        bundle = {
            "schema": BUNDLE_SCHEMA,
            "publisherVersion": compiler.PUBLISHER_VERSION,
            "practiceSet": ready[0]["version"]["metadata"]["practiceSet"],
            "sourceBank": {"sourceQuestionCount": len(questions), "readyQuestionCount": len(ready)},
            "questions": ready,
        }
        dump(bundle_file, bundle)
        validation = subprocess.run([
            sys.executable, str(SCRIPT_DIR / "validate_publish_bundle.py"),
            str(bundle_file), "--bank-root", str(bank),
        ], text=True, capture_output=True, check=False)
        if validation.returncode:
            raise RuntimeError("Ready bundle failed existing publisher validation:\n" + validation.stdout + validation.stderr)
        report["readyBundle"] = str(bundle_file)
    else:
        report["readyBundle"] = None
    # Always save review queues before an optional production request.
    dump(output_dir / "delivery-review-queue.json", report)
    if apply and ready:
        cmd = [sys.executable, str(SCRIPT_DIR / "publish_via_api.py"), str(bundle_file),
               "--bank-root", str(bank), "--apply"]
        result = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError("Publish API rejected ready questions:\n" + result.stdout + result.stderr)
        report["published"] = True
        report["publisherOutput"] = result.stdout.strip()
        dump(output_dir / "delivery-review-queue.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path)
    parser.add_argument("publish_config", type=Path)
    parser.add_argument("reviewed_answers", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="publish ready questions through the existing production API")
    args = parser.parse_args()
    report = run(args.bank, args.publish_config, args.reviewed_answers, args.output_dir, args.apply)
    print(json.dumps({k: report[k] for k in ("sourceQuestionCount", "readyCount", "highPriorityCount", "published")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
