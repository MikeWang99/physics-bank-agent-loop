#!/usr/bin/env python3
"""Read-only diff of a publish bundle against Pocket Cosmos Supabase question versions."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def get_json(base: str, key: str, table: str, params: dict):
    query = urllib.parse.urlencode(params, safe="(),.*")
    req = urllib.request.Request(f"{base.rstrip('/')}/rest/v1/{table}?{query}")
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def build_plan(bundle: dict, base: str, key: str) -> dict:
    items = []
    for item in bundle.get("questions") or []:
        qid = item["question"]["id"]
        digest = item["version"]["contentHash"]
        rows = get_json(base, key, "question_versions", {
            "select": "id,version,content_hash",
            "question_id": f"eq.{qid}",
            "order": "version.desc",
        })
        same = next((r for r in rows if r.get("content_hash") == digest), None)
        latest = max((int(r.get("version") or 0) for r in rows), default=0)
        items.append({
            "questionId": qid,
            "contentHash": digest,
            "action": "noop" if same else "append_version",
            "existingVersion": same.get("version") if same else None,
            "plannedVersion": same.get("version") if same else latest + 1,
            "assetCount": len(item.get("assets") or []),
            "renderCompatibility": (item.get("renderCompatibility") or {}).get("status"),
        })
    return {
        "schema": "pocket-cosmos-publish-plan/v1",
        "practiceSetId": (bundle.get("practiceSet") or {}).get("id"),
        "questions": items,
        "summary": {
            "noop": sum(v["action"] == "noop" for v in items),
            "appendVersion": sum(v["action"] == "append_version" for v in items),
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    base = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not base or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 2
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    plan = build_plan(bundle, base, key)
    text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
