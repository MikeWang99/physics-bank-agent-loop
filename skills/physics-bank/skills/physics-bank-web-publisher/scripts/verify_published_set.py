#!/usr/bin/env python3
"""Verify a published Pocket Cosmos practice set through its runtime API."""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def fetch_json(url: str, token: str | None):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def verify(bundle: dict, payload: dict) -> list[str]:
    errors = []
    expected_set = bundle.get("practiceSet") or {}
    actual = payload.get("set") if isinstance(payload, dict) else None
    if not isinstance(actual, dict):
        return ["API response has no set object"]
    if actual.get("id") != expected_set.get("id"):
        errors.append(f"practice set id mismatch: {actual.get('id')!r}")
    expected = [item["question"]["legacyQuestionId"] for item in bundle.get("questions") or []]
    steps = actual.get("steps")
    if not isinstance(steps, list):
        return errors + ["API set.steps is not an array"]
    actual_ids = [str(step.get("id") or "") for step in steps if isinstance(step, dict)]
    if actual_ids != expected:
        errors.append("runtime question IDs/order do not match publish bundle")
    for step in steps:
        if isinstance(step, dict) and not step.get("questionVersionId"):
            errors.append(f"{step.get('id')}: questionVersionId missing")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle", type=Path)
    p.add_argument("--base-url", default="https://www.pocket-cosmos.com")
    p.add_argument("--access-token")
    args = p.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    set_id = str((bundle.get("practiceSet") or {}).get("id") or "")

    catalog_url = f"{args.base_url.rstrip('/')}/api/practice/catalog"
    try:
        catalog = fetch_json(catalog_url, args.access_token)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Catalog API failed: HTTP {exc.code}: {body[:500]}")
        return 2
    sets = catalog.get("sets") if isinstance(catalog, dict) else None
    if not isinstance(sets, list) or not any(isinstance(v, dict) and v.get("id") == set_id for v in sets):
        print(f"ERROR: {set_id} is missing from /api/practice/catalog")
        return 1
    print(f"Catalog API OK: {set_id} is discoverable")

    url = f"{args.base_url.rstrip('/')}/api/practice/sets/{urllib.parse.quote(set_id, safe='')}"
    try:
        payload = fetch_json(url, args.access_token)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 403:
            print("Set API returned 403 (locked set). Catalog publication is visible; verify DB state and repeat set/UI verification with an authenticated access token.")
            print(body[:500])
            return 3
        print(f"Runtime API failed: HTTP {exc.code}: {body[:500]}")
        return 2
    errors = verify(bundle, payload)
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print(f"Runtime API OK: {set_id}, {len((payload.get('set') or {}).get('steps') or [])} question(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
