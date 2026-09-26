"""盒型路由：创建/读取/更新/删除盒型、版本管理"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import database as db
from ..engines import dieline, folding, preflight

router = APIRouter(prefix="/api", tags=["Boxes"])


class BoxIn(BaseModel):
    projectId: str
    boxType: str
    label: str
    parameters: dict = {}
    material: str = "350g 白卡"
    notes: str = ""


class BoxUpdate(BaseModel):
    label: Optional[str] = None
    parameters: Optional[dict] = None
    material: Optional[str] = None
    notes: Optional[str] = None


class NewVersion(BaseModel):
    label: Optional[str] = None
    parameters: dict
    material: str = "350g 白卡"
    notes: str = ""


def _box_row_to_dict(row) -> dict:
    return {"id": row["id"], "projectId": row["project_id"],
            "boxType": row["box_type"], "label": row["label"],
            "parameters": json.loads(row["parameters"]),
            "dieline": json.loads(row["dieline"]),
            "folding": json.loads(row["folding"] or "null"),
            "preflight": json.loads(row["preflight"] or "null"),
            "material": row["material"], "notes": row.get("notes") or "",
            "version": row.get("version") or 1,
            "createdAt": row["created_at"], "updatedAt": row["updated_at"]}


@router.post("/boxes")
def create_box(box: BoxIn):
    """生成盒型刀模并入库。"""
    with db.get_db() as conn:
        proj = conn.execute("SELECT id FROM projects WHERE id=?",
                            (box.projectId,)).fetchone()
        if not proj:
            raise HTTPException(404, "项目不存在")
    try:
        dl = dieline.generate(box.boxType, box.parameters)
    except KeyError as e:
        raise HTTPException(400, str(e))
    report = preflight.run_preflight(dl)
    tree = folding.folding_tree(dl)
    bid = db.new_id("BX-")
    ts = db.now()
    dl_dict = _dl_to_dict(dl)
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO boxes (id, project_id, box_type, label, parameters, dieline, folding, preflight, thickness, material, notes, version, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid, box.projectId, dl.box_type, box.label or dl.label,
             json.dumps(box.parameters, ensure_ascii=False),
             json.dumps(dl_dict, ensure_ascii=False),
             json.dumps({"tree": tree}, ensure_ascii=False),
             json.dumps(report.to_dict(), ensure_ascii=False),
             float(box.parameters.get("thickness", 0.45)), box.material,
             box.notes, 1, ts, ts))
        conn.execute("UPDATE projects SET updated_at=? WHERE id=?", (ts, box.projectId))
        row = conn.execute("SELECT * FROM boxes WHERE id=?", (bid,)).fetchone()
    return _box_row_to_dict(row)


def _dl_to_dict(dl) -> dict:
    return {"boxType": dl.box_type, "label": dl.label,
            "parameters": dl.parameters,
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
            "notes": dl.notes, "warnings": dl.warnings}


@router.get("/projects/{pid}/boxes")
def list_boxes(pid: str):
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM boxes WHERE project_id=? ORDER BY updated_at DESC",
            (pid,)).fetchall()
    return [_box_row_to_dict(r) for r in rows]


@router.get("/boxes/{bid}")
def get_box(bid: str):
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM boxes WHERE id=?", (bid,)).fetchone()
        if not row:
            raise HTTPException(404, "盒型不存在")
    return _box_row_to_dict(row)


@router.put("/boxes/{bid}")
def update_box(bid: str, upd: BoxUpdate):
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM boxes WHERE id=?", (bid,)).fetchone()
        if not row:
            raise HTTPException(404, "盒型不存在")
        label = upd.label if upd.label is not None else row["label"]
        params = upd.parameters if upd.parameters is not None else json.loads(row["parameters"])
        material = upd.material if upd.material is not None else row["material"]
        notes = upd.notes if upd.notes is not None else (row.get("notes") or "")
        # 参数变化 → 重新生成刀模
        if upd.parameters is not None:
            try:
                dl = dieline.generate(row["box_type"], params)
            except KeyError as e:
                raise HTTPException(400, str(e))
            report = preflight.run_preflight(dl)
            tree = folding.folding_tree(dl)
            dl_json = json.dumps(_dl_to_dict(dl), ensure_ascii=False)
            pf_json = json.dumps(report.to_dict(), ensure_ascii=False)
            fold_json = json.dumps({"tree": tree}, ensure_ascii=False)
        else:
            dl_json, pf_json, fold_json = row["dieline"], row["preflight"], row["folding"]
        ts = db.now()
        conn.execute(
            "UPDATE boxes SET label=?, parameters=?, dieline=?, folding=?, preflight=?, material=?, notes=?, updated_at=? WHERE id=?",
            (label, json.dumps(params, ensure_ascii=False), dl_json, fold_json, pf_json,
             material, notes, ts, bid))
        row = conn.execute("SELECT * FROM boxes WHERE id=?", (bid,)).fetchone()
    return _box_row_to_dict(row)


@router.delete("/boxes/{bid}")
def delete_box(bid: str):
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM boxes WHERE id=?", (bid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "盒型不存在")
    return {"ok": True}


# ---- 版本管理 ----
@router.get("/boxes/{bid}/versions")
def list_versions(bid: str):
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM box_versions WHERE box_id=? ORDER BY version DESC",
            (bid,)).fetchall()
    return [{"id": r["id"], "boxId": r["box_id"], "version": r["version"],
             "label": r["label"], "parameters": json.loads(r["parameters"]),
             "dieline": json.loads(r["dieline"] or "null"),
             "material": r["material"], "notes": r["notes"],
             "createdAt": r["created_at"]} for r in rows]


@router.post("/boxes/{bid}/versions")
def create_version(bid: str, nv: NewVersion):
    with db.get_db() as conn:
        box = conn.execute("SELECT * FROM boxes WHERE id=?", (bid,)).fetchone()
        if not box:
            raise HTTPException(404, "盒型不存在")
        try:
            dl = dieline.generate(box["box_type"], nv.parameters)
        except KeyError as e:
            raise HTTPException(400, str(e))
        report = preflight.run_preflight(dl)
        max_v = conn.execute(
            "SELECT COALESCE(MAX(version),0) m FROM box_versions WHERE box_id=?",
            (bid,)).fetchone()["m"]
        new_v = max_v + 1
        ts = db.now()
        conn.execute(
            "INSERT INTO box_versions (id, box_id, version, label, parameters, dieline, material, notes, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (db.new_id("BV-"), bid, new_v, nv.label or box["label"],
             json.dumps(nv.parameters, ensure_ascii=False),
             json.dumps(_dl_to_dict(dl), ensure_ascii=False),
             nv.material, nv.notes, ts))
    return {"version": new_v, "id": db.new_id("BV-")}
