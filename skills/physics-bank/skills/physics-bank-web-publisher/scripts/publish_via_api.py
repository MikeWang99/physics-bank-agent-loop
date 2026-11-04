#!/usr/bin/env python3
"""Plan or publish a validated Pocket Cosmos bundle through its production API."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEFAULT_API = "https://www.pocket-cosmos.com/api/ai/physics-bank/imports"
DEFAULT_TOKEN_FILE = Path.home() / ".codex/secrets/physics-bank-publisher.env"


def read_token() -> str:
    value = os.environ.get("PHYSICS_BANK_PUBLISH_TOKEN", "").strip()
    if value:
        return value
    if DEFAULT_TOKEN_FILE.is_file():
        for line in DEFAULT_TOKEN_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, content = line.partition("=")
            if separator and key.strip() == "PHYSICS_BANK_PUBLISH_TOKEN":
                return content.strip().strip("\"'")
    return ""


def api_call(url: str, token: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Authorization", "Bearer " + token)
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Pocket Cosmos API returned HTTP {error.code}: {message[:1000]}") from error


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_assets(bundle: dict, bank_root: Path) -> list[dict]:
    by_path = {}
    for item in bundle.get("questions") or []:
        for asset in item.get("assets") or []:
            path = str(asset.get("storagePath") or "")
            current = by_path.get(path)
            if current and current.get("sha256") != asset.get("sha256"):
                raise ValueError(f"storage path collision with different hashes: {path}")
            if current:
                continue
            local = (bank_root / str(asset.get("localFile") or "")).resolve()
            if not local.is_file():
                raise ValueError(f"asset file not found: {local}")
            if local.stat().st_size != int(asset.get("size") or -1):
                raise ValueError(f"asset size changed after compilation: {local}")
            if file_sha256(local) != asset.get("sha256"):
                raise ValueError(f"asset hash changed after compilation: {local}")
            if asset.get("storageBucket") != "question-assets":
                raise ValueError(f"unsupported asset bucket: {asset.get('storageBucket')}")
            by_path[path] = {**asset, "localPath": local}
    return [by_path[path] for path in sorted(by_path)]


def upload_signed(upload: dict, data: bytes, content_type: str) -> str:
    request = urllib.request.Request(str(upload["signedUrl"]), data=data, method="PUT")
    request.add_header("Content-Type", content_type)
    request.add_header("Cache-Control", "max-age=3600")
    request.add_header("x-upsert", "false")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response.read()
        return "uploaded"
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace").casefold()
        if error.code == 400 and ("already exists" in body or "duplicate" in body):
            return "already present"
        raise RuntimeError(f"Supabase Storage upload failed with HTTP {error.code} for {upload.get('path')}") from error


def print_plan(plan: dict) -> None:
    counts = plan.get("counts") or {}
    print("Set: " + str(plan.get("practiceSetId")))
    print("Operation: " + str(plan.get("practiceSetAction")))
    print(
        "Questions: "
        + str(plan.get("questionCount"))
        + "  add="
        + str(counts.get("added", 0))
        + "  update="
        + str(counts.get("changed", 0))
        + "  unchanged="
        + str(counts.get("skipped", 0))
    )
    for question in plan.get("questions") or []:
        print(
            str(question.get("action"))
            + " v"
            + str(question.get("targetVersion"))
            + " "
            + str(question.get("id"))
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--bank-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="upload assets and publish the production bundle")
    parser.add_argument("--api-url", default=os.environ.get("POCKET_COSMOS_PUBLISH_API", DEFAULT_API))
    args = parser.parse_args()

    token = read_token()
    if not token:
        print(
            "Set PHYSICS_BANK_PUBLISH_TOKEN or add it to "
            + str(DEFAULT_TOKEN_FILE),
            file=sys.stderr,
        )
        return 2

    bundle_path = args.bundle.resolve()
    bank_root = args.bank_root.resolve()
    bundle_bytes = bundle_path.read_bytes()
    bundle = json.loads(bundle_bytes.decode("utf-8"))
    assets = unique_assets(bundle, bank_root)
    descriptors = [
        {
            "bucket": "question-assets",
            "path": asset["storagePath"],
            "sha256": asset["sha256"],
            "size": asset["size"],
            "contentType": asset["contentType"],
        }
        for asset in assets
    ]
    prepare = api_call(args.api_url, token, {
        "action": "prepare",
        "manifest": {
            "sha256": hashlib.sha256(bundle_bytes).hexdigest(),
            "size": len(bundle_bytes),
        },
        "assets": descriptors,
    })
    import_id = str(prepare["importId"])
    manifest_upload = prepare["manifestUpload"]
    upload_signed(manifest_upload, bundle_bytes, "application/json")

    planned = api_call(args.api_url, token, {
        "action": "plan",
        "importId": import_id,
        "keepForPublish": args.apply,
    })
    print_plan(planned["plan"])
    if not args.apply:
        print("Plan only. No question versions or images were published. Re-run with --apply to publish.")
        return 0

    uploads_by_path = {item["path"]: item for item in prepare.get("assetUploads") or []}
    jobs = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for asset in assets:
            upload = uploads_by_path.get(asset["storagePath"])
            if not upload:
                raise RuntimeError("The API did not return an upload link for " + asset["storagePath"])
            jobs[executor.submit(upload_signed, upload, asset["localPath"].read_bytes(), asset["contentType"])] = asset
        for future in as_completed(jobs):
            asset = jobs[future]
            print(future.result() + ": " + str(asset["storagePath"]))

    published = api_call(args.api_url, token, {"action": "publish", "importId": import_id})
    print(json.dumps(published, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
