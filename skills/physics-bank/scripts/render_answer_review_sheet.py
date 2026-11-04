#!/usr/bin/env python3
"""Render an auditable visual contact sheet for one worked answer.

Source pixels stay unchanged. Green = retained solution diagrams;
orange = explicitly excluded non-instructional marks.
This is a review aid, NOT an automated judgement of physics correctness.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import fitz
from PIL import Image, ImageDraw

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("questions", type=Path)
    p.add_argument("--assets", required=True, type=Path)
    p.add_argument("--question-id", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--zoom", type=float, default=2.0)
    args=p.parse_args()
    root=args.questions.parent
    questions=json.loads(args.questions.read_text(encoding="utf-8")).get("questions") or []
    q=next((q for q in questions if str(q.get("id"))==args.question_id),None)
    if q is None:
        raise SystemExit(f"question not found: {args.question_id}")
    ans=q.get("answer") or {}
    if ans.get("kind")!="worked_solution":
        raise SystemExit("review sheet requires answer.kind=worked_solution")
    src=ans.get("source") or {}
    file=src.get("file")
    bbox=src.get("bbox")
    page=src.get("page")
    if not file or not isinstance(page,int) or not isinstance(bbox,list) or len(bbox)!=4:
        raise SystemExit("answer.source requires file/page/bbox")
    source=(root/file).resolve() if not Path(file).is_absolute() else Path(file)
    if not source.is_file():
        raise SystemExit(f"source not found: {source}")
    doc=fitz.open(source)
    if not 1<=page<=doc.page_count:
        raise SystemExit("answer source page out of bounds")
    original=doc[page-1]
    region=fitz.Rect(*bbox)
    if region.width<=0 or region.height<=0 or not original.rect.contains(region):
        raise SystemExit("answer source bbox invalid/out of page")
    zoom=args.zoom
    if zoom<=0 or zoom>6:
        raise SystemExit("zoom must be >0 and <=6")
    pix=original.get_pixmap(matrix=fitz.Matrix(zoom,zoom),clip=region,alpha=False)
    canvas=Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
    draw=ImageDraw.Draw(canvas)
    assets=json.loads(args.assets.read_text(encoding="utf-8")).get("assets") or []
    asset_index={str(a.get("id")):a for a in assets}
    regions=[]
    def overlay(box,color,caption,kind):
        if not isinstance(box,list) or len(box)!=4:
            raise SystemExit(f"invalid {kind} bbox")
        r=fitz.Rect(*box)
        if not region.contains(r) or r.width<=0 or r.height<=0:
            raise SystemExit(f"{kind} bbox must be within answer.source.bbox")
        coords=[round((r.x0-region.x0)*zoom),round((r.y0-region.y0)*zoom),
                round((r.x1-region.x0)*zoom),round((r.y1-region.y0)*zoom)]
        draw.rectangle(coords,outline=color,width=3)
        draw.text((coords[0]+3,coords[1]+3),caption,fill=color)
        regions.append({"kind":kind,"label":caption,"bbox":[float(x) for x in box]})
    for aid in ans.get("asset_ids") or []:
        asset=asset_index.get(str(aid))
        if not asset:
            raise SystemExit(f"missing answer asset: {aid}")
        region_meta=asset.get("source") or {}
        if region_meta.get("file")==file and region_meta.get("page")==page:
            overlay(region_meta.get("bbox"),(16,130,50),f"KEEP {aid}","answer_diagram")
    for idx,item in enumerate(ans.get("excluded_non_instructional") or [],1):
        if isinstance(item,dict):
            overlay(item.get("source_bbox"),(200,100,0),f"EXCLUDE {idx}","excluded_mark")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(args.output)
    report={
        "schema":"physics-answer-review-sheet/v1",
        "question_id":args.question_id,
        "source_file":file,
        "source_page":page,
        "source_bbox":[float(v) for v in bbox],
        "source_sha256":sha(source),
        "sheet_file":str(args.output.resolve()),
        "sheet_sha256":sha(args.output),
        "regions":regions,
        "instructional_text":ans.get("text") or "",
        "notice":"Human or vision-model review must compare the original source and this contact sheet; no automatic completeness guarantee."
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Answer review sheet: {args.output}")
    print(f"Answer review report: {args.report}")

if __name__=="__main__":
    main()
