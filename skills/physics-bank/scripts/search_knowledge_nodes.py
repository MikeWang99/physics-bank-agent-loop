#!/usr/bin/env python3
"""Search REAL nodes for candidate comparison, never auto-create or auto-approve UIDs."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from knowledge_taxonomy import load_knowledge_taxonomy

def candidates(taxonomy, query: str, limit: int = 12) -> list[dict]:
    terms = [t for t in re.split(r"[^\w\u4e00-\u9fff]+", query.casefold()) if len(t) >= 2]
    if not terms:
        return []
    out = []
    for node in taxonomy["by_uid"].values():
        name = (node["name_en"] + " " + node["name_zh"] + " " + node["id"]).casefold()
        score = sum(4 if name == t else 2 if name.startswith(t) else 1 if t in name else 0 for t in terms)
        if score:
            out.append((score, node))
    out.sort(key=lambda x: (-x[0], -x[1]["level"], x[1]["id"]))
    return [node for _, node in out[:limit]]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--taxonomy", required=True, type=Path)
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=12)
    args = p.parse_args()
    source = load_knowledge_taxonomy(args.taxonomy)
    print(json.dumps({"version": source["version"], "sha256": source["sha256"],
                      "notice": "Candidate lookup only. Classify after verified physics solution and independent review.",
                      "candidates": candidates(source, args.query, args.limit)}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
