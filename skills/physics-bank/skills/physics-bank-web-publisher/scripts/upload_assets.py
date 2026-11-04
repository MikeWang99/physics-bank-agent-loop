#!/usr/bin/env python3
"""Upload content-addressed publish-bundle assets to Supabase Storage."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def unique_assets(bundle: dict) -> list[dict]:
    by_path = {}
    for item in bundle.get("questions") or []:
        for asset in item.get("assets") or []:
            path = str(asset.get("storagePath") or "")
            if not path:
                continue
            current = by_path.get(path)
            if current and current.get("sha256") != asset.get("sha256"):
                raise ValueError(f"storage path collision with different hashes: {path}")
            by_path[path] = asset
    return [by_path[k] for k in sorted(by_path)]


def upload_one(url: str, key: str, asset: dict, bank_root: Path) -> str:
    bucket = str(asset["storageBucket"])
    path = str(asset["storagePath"])
    local = bank_root / str(asset["localFile"])
    quoted = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    endpoint = f"{url.rstrip('/')}/storage/v1/object/{urllib.parse.quote(bucket, safe='')}/{quoted}"
    data = local.read_bytes()
    req = urllib.request.Request(endpoint, data=data, method="POST")
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", str(asset.get("contentType") or "application/octet-stream"))
    req.add_header("x-upsert", "false")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            response.read()
        return "uploaded"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        low = body.casefold()
        if exc.code == 400 and ("already exists" in low or "duplicate" in low):
            return "exists"
        raise RuntimeError(f"upload failed {exc.code} {path}: {body[:500]}") from exc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle", type=Path)
    p.add_argument("--bank-root", required=True, type=Path)
    p.add_argument("--apply", action="store_true", help="perform uploads; default is plan only")
    args = p.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    assets = unique_assets(bundle)
    print(f"Assets to ensure: {len(assets)}")
    for asset in assets:
        print(f"- {asset['storageBucket']}/{asset['storagePath']} <- {asset['localFile']}")
    if not args.apply:
        print("Plan only. Re-run with --apply to upload.")
        return 0

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for --apply", file=sys.stderr)
        return 2

    uploaded = existing = 0
    for asset in assets:
        state = upload_one(url, key, asset, args.bank_root.resolve())
        uploaded += state == "uploaded"
        existing += state == "exists"
        print(f"{state}: {asset['storagePath']}")
    print(f"Storage complete: uploaded={uploaded}, already_present={existing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
