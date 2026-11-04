#!/usr/bin/env python3
"""Verify exact published hashes and assets through Supabase PostgREST."""
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


def verify(bundle: dict, base: str, key: str) -> list[str]:
    errors = []
    for item in bundle.get("questions") or []:
        qid = item["question"]["id"]
        digest = item["version"]["contentHash"]
        qrows = get_json(base, key, "questions", {
            "select": "id,practice_set_id,legacy_question_id,status,position",
            "id": f"eq.{qid}",
        })
        if len(qrows) != 1:
            errors.append(f"{qid}: stable question row missing/duplicated")
            continue
        if qrows[0].get("position") != item["question"]["position"]:
            errors.append(f"{qid}: position mismatch")

        versions = get_json(base, key, "question_versions", {
            "select": "id,version,content_hash",
            "question_id": f"eq.{qid}",
            "content_hash": f"eq.{digest}",
        })
        if len(versions) != 1:
            errors.append(f"{qid}: exact content hash not published exactly once")
            continue
        vid = versions[0]["id"]
        rows = get_json(base, key, "question_assets", {
            "select": "role,storage_bucket,storage_path,choice_key,sort_order",
            "question_version_id": f"eq.{vid}",
        })
        expected = {
            (
                a["role"], a["storageBucket"], a["storagePath"],
                a.get("choiceKey"), int(a.get("sortOrder", 0))
            )
            for a in item.get("assets") or []
        }
        actual = {
            (
                a.get("role"), a.get("storage_bucket"), a.get("storage_path"),
                a.get("choice_key"), int(a.get("sort_order") or 0)
            )
            for a in rows
        }
        if actual != expected:
            errors.append(f"{qid}: question_assets mismatch for published version")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle", type=Path)
    args = p.parse_args()
    base = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not base or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 2
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    errors = verify(bundle, base, key)
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print(f"Database verification OK: {len(bundle.get('questions') or [])} question(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
