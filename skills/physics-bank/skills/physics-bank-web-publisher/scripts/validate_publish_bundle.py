#!/usr/bin/env python3
"""Validate a Pocket Cosmos publish bundle before storage/database mutation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "pocket-cosmos-publish-bundle/v1"


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def recompute_hash(item: dict) -> str:
    v = item["version"]
    basis = {
        "stem": v["stem"],
        "choices": v["choices"],
        "answer": v["answer"],
        "metadata": v["metadata"],
        "sourceYear": v.get("sourceYear"),
        "sourceRef": v.get("sourceRef"),
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
            for a in item.get("assets") or []
        ],
    }
    return hashlib.sha256(compact(basis).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(bundle: dict, bank_root: Path) -> list[str]:
    errors = []
    if bundle.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    ps = bundle.get("practiceSet")
    if not isinstance(ps, dict) or not ps.get("id"):
        errors.append("practiceSet.id is required")
        ps = {}
    items = bundle.get("questions")
    if not isinstance(items, list) or not items:
        errors.append("questions must be a non-empty array")
        return errors

    ids, local_ids, positions, storage_paths = set(), set(), set(), set()
    for n, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"questions[{n}] must be an object")
            continue
        q = item.get("question") or {}
        v = item.get("version") or {}
        qid = str(q.get("id") or "")
        local = str(q.get("legacyQuestionId") or "")
        prefix = f"{ps.get('id')}::"
        if not qid.startswith(prefix):
            errors.append(f"{qid or f'questions[{n}]'}: stable id must start with {prefix}")
        if qid in ids:
            errors.append(f"{qid}: duplicate stable question id")
        ids.add(qid)
        if not local or local in local_ids:
            errors.append(f"{qid}: legacyQuestionId must be unique/non-empty")
        local_ids.add(local)
        pos = q.get("position")
        if not isinstance(pos, int) or pos < 0 or pos in positions:
            errors.append(f"{qid}: position must be a unique non-negative integer")
        positions.add(pos)

        if q.get("practiceSetId") != ps.get("id"):
            errors.append(f"{qid}: practiceSetId mismatch")
        if not str(v.get("stem") or "").strip():
            errors.append(f"{qid}: version.stem is empty")
        meta = v.get("metadata")
        if not isinstance(meta, dict):
            errors.append(f"{qid}: metadata is required")
            meta = {}
        if meta.get("formatVersion") != 2:
            errors.append(f"{qid}: metadata.formatVersion must be 2")
        if (meta.get("practiceSet") or {}).get("id") != ps.get("id"):
            errors.append(f"{qid}: metadata.practiceSet.id mismatch")
        step = meta.get("practiceStep") if isinstance(meta.get("practiceStep"), dict) else {}
        pb = meta.get("physicsBank")
        if not isinstance(pb, dict) or pb.get("schema") != "physics-bank-web-publish/v1":
            errors.append(f"{qid}: metadata.physicsBank must preserve publisher provenance")
        else:
            c = pb.get("classification") or {}
            if c.get("schema") == "physics-question-classification/v2":
                uid = c.get("primary_knowledge_uid")
                if not uid or pb.get("primaryKnowledgeUid") != uid or step.get("primaryKnowledgeUid") != uid:
                    errors.append(f"{qid}: v2 primary knowledge UID missing or not preserved in runtime metadata")
                if not pb.get("sourceSystem") or step.get("sourceSystem") != pb.get("sourceSystem"):
                    errors.append(f"{qid}: source system lost during publication")
                if not (pb.get("knowledgeTaxonomy") or {}).get("sha256"):
                    errors.append(f"{qid}: missing taxonomy hash provenance")
            if "classification" not in pb:
                errors.append(f"{qid}: physicsBank.classification missing")
            if "layoutBlocks" not in pb:
                errors.append(f"{qid}: physicsBank.layoutBlocks missing")

        compat = item.get("renderCompatibility") or {}
        if compat.get("status") not in {"native", "degraded"}:
            errors.append(f"{qid}: renderCompatibility status must be native/degraded after compile")

        digest = str(v.get("contentHash") or "")
        if len(digest) != 64 or digest != recompute_hash(item):
            errors.append(f"{qid}: stale/invalid contentHash")

        choice_labels = {str(c.get("label") or "") for c in (v.get("choices") or []) if isinstance(c, dict)}
        for a in item.get("assets") or []:
            path = str(a.get("storagePath") or "")
            if not path:
                errors.append(f"{qid}: asset storagePath missing")
            if path in storage_paths:
                # Reuse is valid for a physically shared asset; don't reject identical path.
                pass
            storage_paths.add(path)
            rel = str(a.get("localFile") or "")
            local_path = bank_root / rel
            if not local_path.is_file():
                errors.append(f"{qid}: local asset missing: {rel}")
            else:
                actual = file_hash(local_path)
                if actual != a.get("sha256"):
                    errors.append(f"{qid}: asset SHA mismatch: {rel}")
                if actual[:12] not in path:
                    errors.append(f"{qid}: storage path is not content-addressed: {path}")
            role = a.get("role")
            slot = (a.get("metadata") or {}).get("slot")
            if role == "choice":
                key = str(a.get("choiceKey") or "")
                if key not in choice_labels:
                    errors.append(f"{qid}: choice asset bound to unknown choice {key!r}")
                if slot not in {"choices.image", "choices.images"}:
                    errors.append(f"{qid}: choice asset has invalid slot {slot!r}")
            elif role == "stem":
                if slot != "image":
                    errors.append(f"{qid}: stem asset slot must be image")
            elif role == "figure":
                if slot != "supportingImages":
                    errors.append(f"{qid}: figure asset slot must be supportingImages")
            elif role == "answer":
                if slot not in {"solutionImage", "answerAssets"}:
                    errors.append(f"{qid}: answer image slot must be solutionImage/answerAssets")
                if a.get("choiceKey") is not None:
                    errors.append(f"{qid}: answer image must not have a choiceKey")
            else:
                errors.append(f"{qid}: unsupported publish asset role {role!r}")

    expected_positions = set(range(len(items)))
    if positions != expected_positions:
        errors.append("question positions must be contiguous 0..N-1")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle", type=Path)
    p.add_argument("--bank-root", required=True, type=Path)
    args = p.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    errors = validate(bundle, args.bank_root.resolve())
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print(f"Publish bundle OK: {len(bundle.get('questions') or [])} question(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
