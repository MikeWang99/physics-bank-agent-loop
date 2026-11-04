#!/usr/bin/env python3
"""Read the single Pocket Cosmos taxonomy authority without creating new UIDs."""
from __future__ import annotations
import hashlib
import json
import re
import uuid
from pathlib import Path

LOCK = Path(__file__).resolve().parents[1] / "references/knowledge-taxonomy.lock.json"

def source_hash(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def load_knowledge_taxonomy(path: Path, *, verify_lock: bool = True) -> dict:
    """Return validated nodes, paths, SHA-256 and version from a JSON source."""
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if verify_lock and source_hash(raw) != lock["git_blob_sha1"]:
        raise ValueError("taxonomy bytes differ from the pinned website Git blob; explicitly update lock after reviewing source changes")
    if not isinstance(data, dict) or not isinstance(data.get("taxonomy"), list):
        raise ValueError("knowledge taxonomy must contain taxonomy[]")
    version = (data.get("metadata") or {}).get("version")
    if verify_lock and version != lock["taxonomy_version"]:
        raise ValueError("knowledge taxonomy version differs from pinned source")
    by_uid, by_code = {}, {}
    counts = {str(i): 0 for i in range(1, 6)}
    def visit(node, parent=None, depth=1, ancestry=()):
        if not isinstance(node, dict) or not isinstance(node.get("children"), list):
            raise ValueError("knowledge node must be an object with children[]")
        code, uid = node.get("id"), node.get("uid")
        if not isinstance(code, str) or not code or not isinstance(uid, str):
            raise ValueError("knowledge node requires code and UID")
        try:
            if str(uuid.UUID(uid)) != uid:
                raise ValueError("UID must be canonical")
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"invalid knowledge UID {uid!r}") from exc
        if uid in by_uid or code in by_code:
            raise ValueError(f"duplicate knowledge UID/code: {uid}, {code}")
        if node.get("parent_id") != (parent["id"] if parent else None):
            raise ValueError(f"invalid parent_id for {code}")
        if depth > 5 or node.get("level") != depth or (parent and not code.startswith(parent["id"] + ".")):
            raise ValueError(f"invalid knowledge hierarchy at {code}")
        if not all(isinstance(node.get(k), str) and node[k].strip() for k in ("name_en", "name_zh")):
            raise ValueError(f"missing bilingual knowledge names at {code}")
        if not isinstance(node.get("order"), int) or node["order"] < 0:
            raise ValueError(f"invalid order at {code}")
        info = {k: node[k] for k in ("id", "uid", "level", "order", "name_en", "name_zh")}
        info["path"] = list(ancestry) + [code]
        by_uid[uid], by_code[code] = info, info
        counts[str(depth)] += 1
        for child in node["children"]:
            visit(child, node, depth + 1, tuple(info["path"]))
    for root in data["taxonomy"]:
        visit(root)
    expected = (data.get("metadata") or {}).get("counts") or {}
    if any(expected.get(k) != v for k, v in counts.items()):
        raise ValueError("knowledge taxonomy level counts disagree with metadata")
    if verify_lock and len(by_uid) != lock["expected_nodes"]:
        raise ValueError("knowledge taxonomy node count differs from lock")
    return {"by_uid": by_uid, "by_code": by_code, "version": version,
            "sha256": hashlib.sha256(raw).hexdigest(), "count": len(by_uid)}

def validate_uid(uid: str, taxonomy: dict) -> bool:
    return isinstance(uid, str) and uid in taxonomy["by_uid"]
