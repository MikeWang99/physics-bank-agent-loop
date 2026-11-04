#!/usr/bin/env python3
"""Verify an explicit export from the website's pinned taxonomy and cache it locally.

Example:
  python scripts/sync_knowledge_taxonomy.py \
    --input ../pocket-cosmos-online/src/data/pocket_cosmos_physics_taxonomy_v1.json \
    --output question-bank/knowledge-taxonomy.json
The website repo/commit and Git blob SHA-1 live in references/knowledge-taxonomy.lock.json.
No second hand-maintained tree is permitted.
"""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path
from knowledge_taxonomy import load_knowledge_taxonomy, LOCK

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    taxonomy = load_knowledge_taxonomy(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.input.resolve() != args.output.resolve():
        shutil.copyfile(args.input, args.output)
    print(json.dumps({"lock": json.loads(LOCK.read_text(encoding="utf-8")),
                      "sha256": taxonomy["sha256"], "version": taxonomy["version"],
                      "nodes": taxonomy["count"], "output": str(args.output)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
