"""导出路由：SVG / DXF / PDF 刀模导出"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Response

from .. import database as db
from ..engines import export as exp

router = APIRouter(prefix="/api/boxes", tags=["Export"])


@router.get("/{bid}/export/svg")
def export_svg(bid: str):
    with db.get_db() as conn:
        row = conn.execute("SELECT dieline FROM boxes WHERE id=?", (bid,)).fetchone()
    if not row:
        raise HTTPException(404, "盒型不存在")
    dl = _load_dieline(json.loads(row["dieline"]))
    return Response(exp.export_svg(dl), media_type="image/svg+xml",
                    headers={"Content-Disposition": f"attachment; filename={bid}.svg"})


@router.get("/{bid}/export/dxf")
def export_dxf(bid: str):
    with db.get_db() as conn:
        row = conn.execute("SELECT dieline FROM boxes WHERE id=?", (bid,)).fetchone()
    if not row:
        raise HTTPException(404, "盒型不存在")
    dl = _load_dieline(json.loads(row["dieline"]))
    return Response(exp.export_dxf(dl), media_type="application/dxf",
                    headers={"Content-Disposition": f"attachment; filename={bid}.dxf"})


@router.get("/{bid}/export/pdf")
def export_pdf(bid: str):
    with db.get_db() as conn:
        row = conn.execute("SELECT dieline FROM boxes WHERE id=?", (bid,)).fetchone()
    if not row:
        raise HTTPException(404, "盒型不存在")
    dl = _load_dieline(json.loads(row["dieline"]))
    return Response(exp.export_pdf(dl), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={bid}.pdf"})


def _load_dieline(data: dict):
    """把 JSON 还原为 DielineData 对象（供导出引擎复用）。"""
    from ..engines.dieline import DielineData, DielinePiece, FoldSpec, PanelSpec
    pieces = []
    for p in data.get("pieces", []):
        panels = {k: PanelSpec(id=v["id"], role=v["role"], name=v["name"],
                               points=[tuple(x) for x in v["points"]],
                               holes=[[tuple(y) for y in h] for h in v.get("holes", [])],
                               extra=v.get("extra", {}))
                  for k, v in p["panels"].items()}
        folds = [FoldSpec(a=f["a"], b=f["b"], angle=f["angle"]) for f in p.get("folds", [])]
        pieces.append(DielinePiece(label=p["label"], panels=panels, folds=folds))
    return DielineData(box_type=data.get("boxType", "tuck-end"),
                       label=data.get("label", "盒型"),
                       parameters=data.get("parameters", {}),
                       pieces=pieces,
                       flat_width=data.get("flatWidth", 0),
                       flat_height=data.get("flatHeight", 0))
