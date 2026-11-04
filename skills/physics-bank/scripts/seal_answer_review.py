#!/usr/bin/env python3
"""Seal a manually inspected worked-answer visual review against source and sheet SHA.

The flags are explicit reviewer attestations. The script cannot prove that a
vision model or human actually looked at the page or understood the physics.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("questions",type=Path)
    p.add_argument("--assets",required=True,type=Path)
    p.add_argument("--question-id",required=True)
    p.add_argument("--review-report",required=True,type=Path)
    p.add_argument("--method",default="original-source+review-sheet-visual")
    p.add_argument("--confirm-complete-text",action="store_true")
    p.add_argument("--confirm-math",action="store_true")
    p.add_argument("--confirm-diagrams",action="store_true")
    p.add_argument("--confirm-exclusions",action="store_true")
    args=p.parse_args()
    if not all([args.confirm_complete_text,args.confirm_math,args.confirm_diagrams]):
        raise SystemExit("must visually confirm complete text, math and diagrams")
    root=args.questions.parent
    data=json.loads(args.questions.read_text(encoding="utf-8"))
    question=next((q for q in data.get("questions") or [] if str(q.get("id"))==args.question_id),None)
    if question is None:
        raise SystemExit("question id not found")
    answer=question.get("answer") or {}
    if answer.get("kind")!="worked_solution":
        raise SystemExit("answer.kind must be worked_solution")
    if answer.get("excluded_non_instructional") and not args.confirm_exclusions:
        raise SystemExit("excluded marks must be visually confirmed as non-instructional")
    if (answer.get("extraction") or {}).get("reviewed") is not True:
        raise SystemExit("answer.extraction.reviewed must be true after source transcription")
    report=json.loads(args.review_report.read_text(encoding="utf-8"))
    source=answer.get("source") or {}
    source_file=str(source.get("file") or "")
    source_path=(root/source_file).resolve() if source_file and not Path(source_file).is_absolute() else Path(source_file)
    sheet=Path(report.get("sheet_file") or "")
    if report.get("schema")!="physics-answer-review-sheet/v1" or report.get("question_id")!=args.question_id:
        raise SystemExit("review report does not match answer/question")
    if not sheet.is_file() or sha(sheet)!=report.get("sheet_sha256"):
        raise SystemExit("review sheet changed or is missing")
    if not source_path.is_file() or sha(source_path)!=report.get("source_sha256"):
        raise SystemExit("original answer source changed or is missing")
    if report.get("source_file")!=source_file or report.get("source_page")!=source.get("page"):
        raise SystemExit("reviewed source document/page differs from answer.source")
    if report.get("source_bbox")!=[float(v) for v in (source.get("bbox") or [])]:
        raise SystemExit("review sheet bbox differs from answer.source")
    # Reject stale sheets if the answer prose/asset/exclusion mapping has changed.
    if report.get("instructional_text")!=(answer.get("text") or ""):
        raise SystemExit("answer text changed since the review sheet was built; re-render and inspect")
    assets=json.loads(args.assets.read_text(encoding="utf-8")).get("assets") or []
    index={str(a.get("id")):a for a in assets}
    expected=[]
    for aid in answer.get("asset_ids") or []:
        src=(index.get(str(aid)) or {}).get("source") or {}
        if src.get("file")==source_file and src.get("page")==source.get("page"):
            expected.append(("answer_diagram",f"KEEP {aid}",[float(v) for v in src.get("bbox") or []]))
    for i,item in enumerate(answer.get("excluded_non_instructional") or [],1):
        expected.append(("excluded_mark",f"EXCLUDE {i}",[float(v) for v in item.get("source_bbox") or []]))
    observed=[(v.get("kind"),v.get("label"),v.get("bbox")) for v in report.get("regions") or []]
    if expected!=observed:
        raise SystemExit("review sheet regions are stale; re-render and inspect")
    review={
        "reviewed":True,
        "method":args.method,
        "source_sha256":report["source_sha256"],
        "page":source["page"],
        "bbox":[float(v) for v in source["bbox"]],
        "review_sheet_sha256":report["sheet_sha256"],
        "instructional_text_complete":True,
        "equations_checked":True,
        "diagrams_checked":True,
        "exclusions_checked":bool(args.confirm_exclusions or not answer.get("excluded_non_instructional"))
    }
    answer["visual_review"]=review

    # Reuse strict geometry/hash checker to avoid sealing overlapping exclusions.
    spec=importlib.util.spec_from_file_location("bank_validator",Path(__file__).with_name("validate_bank.py"))
    validator=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validator)
    issues=validator.validate_answer_visual_review(question,index,root,strict=True)
    if issues:
        raise SystemExit("review cannot be sealed:\n"+"\n".join(issues))

    args.questions.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Sealed worked-answer source visual review: {args.question_id}")

if __name__=="__main__":
    main()
