#!/usr/bin/env python3
"""Canonicalize final visual-choice assets for physics-bank v2.2.

Choice images are published under:
  assets/choices/<question-id>/<LABEL>-<NN>.<ext>

The script never marks an image reviewed. It only accepts choice assets that
were already visually reviewed after their last crop and explicitly marked
`crop.isolated_choice: true`.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_label(value) -> str:
    return str(value or "").strip().upper()


def canonical_relative(qid: str, label: str, index: int, suffix: str) -> Path:
    return Path("assets") / "choices" / qid / f"{label}-{index:02d}{suffix.lower()}"


def organize(questions_path: Path, assets_path: Path, apply: bool = False) -> dict:
    root = questions_path.parent
    qdata = load(questions_path)
    adata = load(assets_path)
    questions = qdata.get("questions") or []
    assets = adata.get("assets") or []
    qindex = {str(q.get("id")): q for q in questions if q.get("id")}

    errors: list[str] = []
    actions: list[dict] = []
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for asset in assets:
        if asset.get("role") != "choice":
            continue
        aid = str(asset.get("id") or "")
        owners = [str(v) for v in (asset.get("owners") or [])]
        label = normalize_label(asset.get("choice_label"))
        file_value = str(asset.get("file") or asset.get("path") or "")
        crop = asset.get("crop") or {}

        if not aid:
            errors.append("choice asset missing id")
            continue
        if len(owners) != 1:
            errors.append(f"{aid}: choice asset must have exactly one owner")
            continue
        qid = owners[0]
        if qid not in qindex:
            errors.append(f"{aid}: unknown owner {qid}")
            continue
        if not label:
            errors.append(f"{aid}: missing choice_label")
            continue
        if not asset.get("reviewed") or crop.get("isolated_choice") is not True:
            errors.append(f"{aid}: must be reviewed and crop.isolated_choice=true before organizing")
            continue
        if not file_value:
            errors.append(f"{aid}: missing file/path")
            continue
        src = Path(file_value) if Path(file_value).is_absolute() else root / file_value
        if not src.exists():
            errors.append(f"{aid}: source file not found: {file_value}")
            continue
        if src.suffix.lower() not in VALID_EXTENSIONS:
            errors.append(f"{aid}: unsupported choice image format {src.suffix}")
            continue
        grouped[(qid, label)].append(asset)

    # Assign deterministic indices. A single image defaults to 1. Multiple
    # images require unique explicit choice_index values to preserve semantics.
    for (qid, label), group in grouped.items():
        explicit = [a.get("choice_index") for a in group]
        if len(group) > 1:
            if any(not isinstance(v, int) or v < 1 for v in explicit) or len(set(explicit)) != len(explicit):
                errors.append(f"{qid} choice {label}: multiple images require unique positive choice_index values")
                continue
            ordered = sorted(group, key=lambda a: int(a["choice_index"]))
        else:
            group[0]["choice_index"] = int(group[0].get("choice_index") or 1)
            ordered = group

        question = qindex[qid]
        choices = question.get("choices") or []
        choice_entry = next((c for c in choices if isinstance(c, dict) and normalize_label(c.get("label")) == label), None)
        if choice_entry is None:
            errors.append(f"{qid} choice {label}: no matching choice entry")
            continue

        bound_ids: list[str] = []
        for asset in ordered:
            aid = str(asset["id"])
            idx = int(asset["choice_index"])
            old_value = str(asset.get("file") or asset.get("path"))
            src = Path(old_value) if Path(old_value).is_absolute() else root / old_value
            rel = canonical_relative(qid, label, idx, src.suffix)
            dst = root / rel
            actions.append({"asset_id": aid, "from": old_value, "to": rel.as_posix()})
            bound_ids.append(aid)
            if apply and src.resolve() != dst.resolve():
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    if dst.read_bytes() != src.read_bytes():
                        errors.append(f"{aid}: canonical target already exists with different content: {rel}")
                        continue
                else:
                    # Files already inside the bank are moved so choice images do
                    # not remain duplicated under assets/figures. External/temp
                    # crops are copied into the bank.
                    try:
                        src.resolve().relative_to(root.resolve())
                        shutil.move(str(src), str(dst))
                    except ValueError:
                        shutil.copy2(src, dst)
            asset["file"] = rel.as_posix()
            asset.pop("path", None)

        choice_entry["asset_ids"] = bound_ids
        top_ids = [str(v) for v in (question.get("asset_ids") or [])]
        for aid in bound_ids:
            if aid not in top_ids:
                top_ids.append(aid)
        question["asset_ids"] = top_ids

    if errors:
        return {"status": "error", "errors": errors, "actions": actions}
    if apply:
        dump(questions_path, qdata)
        dump(assets_path, adata)
    return {"status": "ok", "errors": [], "actions": actions, "applied": bool(apply)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("questions", type=Path)
    ap.add_argument("--assets", type=Path, required=True)
    ap.add_argument("--apply", action="store_true", help="move/copy files and update both JSON files")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    report = organize(args.questions, args.assets, args.apply)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for err in report.get("errors", []):
        print(f"ERROR: {err}")
    for action in report.get("actions", []):
        print(f"{action['asset_id']}: {action['from']} -> {action['to']}")
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
