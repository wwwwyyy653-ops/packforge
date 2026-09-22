"""盒型实例路由：创建/读取/更新/删除 + 3D 折叠 + 几何验证 + 版本 + 成本"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import database as db
from ..engines import dieline, folding, preflight

router = APIRouter(prefix="/api/boxes", tags=["boxes"])


class BoxIn(BaseModel):
    projectId: str
    boxType: str
    parameters: Dict = Field(default_factory=dict)
    material: str = "350g 白卡"
    notes: str = ""
    tags: str = ""


class BoxUpdate(BaseModel):
    boxType: Optional[str] = None
    parameters: Optional[Dict] = None
    material: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[str] = None


class CostQuery(BaseModel):
    quantity: int = Field(gt=0, default=1000)
    grammage: float = Field(gt=0, default=350)
    paperPricePerKg: float = Field(gt=0, default=6.5)
    colors: int = 4
    printType: str = "offset"
    finishes: List[str] = []
    profitRate: float = 0.25


def _dieline_dict(dl) -> dict:
    return {
        "boxType": dl.box_type, "label": dl.label, "parameters": dl.parameters,
        "flatWidth": dl.flat_width, "flatHeight": dl.flat_height,
        "twoPiece": dl.two_piece,
        "pieces": [
            {"label": pc.label,
             "panels": {k: {"id": v.id, "role": v.role, "name": v.name,
                            "points": v.points, "holes": v.holes, "extra": v.extra}
                        for k, v in pc.panels.items()},
             "folds": [{"a": f.a, "b": f.b, "angle": f.angle} for f in pc.folds]}
            for pc in dl.pieces
        ],
        "notes": dl.notes, "warnings": dl.warnings,
    }


def _box_row(r) -> dict:
    return {
        "id": r["id"], "projectId": r["project_id"], "boxType": r["box_type"],
        "label": r["label"],
        "parameters": json.loads(r["parameters"]),
        "dieline": json.loads(r["dieline"]),
        "folding": json.loads(r["folding"]) if r["folding"] else None,
        "preflight": json.loads(r["preflight"]) if r["preflight"] else None,
        "thickness": r["thickness"], "material": r["material"],
        "notes": r["notes"] if "notes" in r.keys() else "",
        "tags": r["tags"] if "tags" in r.keys() else "",
        "version": r["version"] if "version" in r.keys() else 1,
        "createdAt": r["created_at"], "updatedAt": r["updated_at"],
    }


def conn_row(bid: str):
    with db.get_db() as conn:
        r = conn.execute("SELECT * FROM boxes WHERE id=?", (bid,)).fetchone()
    if not r:
        raise HTTPException(404, "盒型不存在")
    return r


@router.get("")
def list_boxes(project_id: Optional[str] = None) -> list:
    with db.get_db() as conn:
        if project_id:
            rows = conn.execute("SELECT * FROM boxes WHERE project_id=? ORDER BY created_at",
                                (project_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM boxes ORDER BY updated_at DESC").fetchall()
        return [_box_row(r) for r in rows]


@router.post("")
def create_box(body: BoxIn) -> dict:
    try:
        dl = dieline.generate(body.boxType, body.parameters)
    except KeyError as e:
        raise HTTPException(400, str(e))
    report = preflight.run_preflight(dl)
    ts = db.now()
    bid = db.new_id("BX-")
    with db.get_db() as conn:
        db._insert(conn, "boxes", {
            "id": bid, "project_id": body.projectId, "box_type": body.boxType,
            "label": dl.label,
            "parameters": json.dumps(body.parameters, ensure_ascii=False),
            "dieline": json.dumps(_dieline_dict(dl), ensure_ascii=False),
            "folding": json.dumps({"tree": folding.folding_tree(dl)}, ensure_ascii=False),
            "preflight": json.dumps(report.to_dict(), ensure_ascii=False),
            "thickness": float(body.parameters.get("thickness", 0.45)),
            "material": body.material,
            "notes": body.notes, "tags": body.tags, "version": 1,
            "created_at": ts, "updated_at": ts})
        conn.execute("UPDATE projects SET updated_at=? WHERE id=?", (ts, body.projectId))
    return _box_row(conn_row(bid))


@router.get("/{box_id}")
def get_box(box_id: str) -> dict:
    return _box_row(conn_row(box_id))


@router.patch("/{box_id}")
def update_box(box_id: str, body: BoxUpdate) -> dict:
    r = conn_row(box_id)
    box_type = body.boxType or r["box_type"]
    params = json.loads(r["parameters"])
    if body.parameters:
        params.update(body.parameters)
    if body.material:
        params.setdefault("material", body.material)
    try:
        dl = dieline.generate(box_type, params)
    except KeyError as e:
        raise HTTPException(400, str(e))
    report = preflight.run_preflight(dl)
    ts = db.now()
    old_version = r["version"] if "version" in r.keys() else 1
    new_version = old_version + 1
    notes = body.notes if body.notes is not None else (r["notes"] if "notes" in r.keys() else "")
    tags = body.tags if body.tags is not None else (r["tags"] if "tags" in r.keys() else "")
    with db.get_db() as conn:
        db._insert(conn, "box_versions", {
            "id": db.new_id("BV-"), "box_id": box_id, "version": old_version,
            "label": r["label"], "parameters": r["parameters"],
            "dieline": r["dieline"], "material": r["material"],
            "notes": r["notes"] if "notes" in r.keys() else "",
            "created_at": r["updated_at"]})
        conn.execute(
            "UPDATE boxes SET box_type=?, label=?, parameters=?, dieline=?, "
            "folding=?, preflight=?, thickness=?, material=?, notes=?, tags=?, "
            "version=?, updated_at=? WHERE id=?",
            (box_type, dl.label, json.dumps(params, ensure_ascii=False),
             json.dumps(_dieline_dict(dl), ensure_ascii=False),
             json.dumps({"tree": folding.folding_tree(dl)}, ensure_ascii=False),
             json.dumps(report.to_dict(), ensure_ascii=False),
             float(params.get("thickness", 0.45)), body.material or r["material"],
             notes, tags, new_version, ts, box_id))
    return _box_row(conn_row(box_id))


@router.get("/{box_id}/versions")
def list_versions(box_id: str) -> list:
    conn_row(box_id)
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT id, box_id, version, label, parameters, material, notes, created_at "
            "FROM box_versions WHERE box_id=? ORDER BY version DESC", (box_id,)).fetchall()
        return [{"id": r["id"], "version": r["version"], "label": r["label"],
                 "parameters": json.loads(r["parameters"]),
                 "material": r["material"], "notes": r["notes"],
                 "createdAt": r["created_at"]} for r in rows]


@router.post("/{box_id}/cost")
def box_cost(box_id: str, body: CostQuery) -> dict:
    r = conn_row(box_id)
    dl_dict = json.loads(r["dieline"])
    flat_w = float(dl_dict.get("flatWidth", 0))
    flat_h = float(dl_dict.get("flatHeight", 0))
    area_m2 = (flat_w * flat_h) / 1_000_000.0
    from ..engines import packtools
    est = packtools.cost_estimate(
        body.quantity, area_m2, body.grammage, body.paperPricePerKg,
        body.colors, body.printType, body.finishes, profit_rate=body.profitRate)
    return {"boxId": box_id, "flatWidthMm": flat_w, "flatHeightMm": flat_h,
            "areaM2": round(area_m2, 4), "estimate": est}


@router.delete("/{box_id}")
def delete_box(box_id: str) -> dict:
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM boxes WHERE id=?", (box_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "盒型不存在")
    return {"deleted": box_id}


@router.post("/{box_id}/folding")
def get_folding(box_id: str, body: dict | None = None) -> dict:
    r = conn_row(box_id)
    dl_dict = json.loads(r["dieline"])
    dl = _rebuild_dieline(dl_dict, r["box_type"])
    progress = float((body or {}).get("progress", 1.0))
    faces = folding.build_folding_3d(dl, progress=progress)
    return {"boxId": box_id, "progress": progress, "faces": faces,
            "tree": folding.folding_tree(dl)}


def _rebuild_dieline(d: dict, box_type: str):
    from ..engines.dieline import DielineData, DielinePiece, PanelSpec, FoldSpec
    pieces = []
    for pc in d.get("pieces", []):
        panels = {}
        for k, v in pc.get("panels", {}).items():
            spec = PanelSpec(id=v.get("id", k), role=v.get("role", ""),
                             name=v.get("name", k), points=[tuple(p) for p in v["points"]],
                             holes=[[tuple(h) for h in hole] for hole in v.get("holes", [])],
                             extra=v.get("extra", {}))
            panels[k] = spec
        folds = [FoldSpec(f["a"], f["b"], f["angle"]) for f in pc.get("folds", [])]
        pieces.append(DielinePiece(pc.get("label", "主体"), panels, folds))
    return DielineData(box_type=box_type, label=d.get("label", ""),
                       parameters=d.get("parameters", {}), pieces=pieces,
                       flat_width=d.get("flatWidth", 0), flat_height=d.get("flatHeight", 0))
