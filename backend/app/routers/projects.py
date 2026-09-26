"""项目路由：项目管理"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import database as db

router = APIRouter(prefix="/api", tags=["Projects"])


class ProjectIn(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.get("/projects")
def list_projects():
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    out = []
    for r in rows:
        stats = conn.execute(
            "SELECT COUNT(*) c, COALESCE(SUM(CASE WHEN preflight LIKE '%\"passed\":true%' THEN 1 ELSE 0 END),0) ok "
            "FROM boxes WHERE project_id=?", (r["id"],)).fetchone()
        out.append({"id": r["id"], "name": r["name"],
                    "description": r["description"], "status": r["status"],
                    "boxCount": stats["c"], "passedCount": stats["ok"],
                    "createdAt": r["created_at"], "updatedAt": r["updated_at"]})
    return out


@router.post("/projects")
def create_project(p: ProjectIn):
    pid = db.new_id("PRJ-")
    ts = db.now()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (pid, p.name, p.description, "draft", ts, ts))
    return {"id": pid, "name": p.name, "description": p.description,
            "status": "draft", "boxCount": 0, "passedCount": 0,
            "createdAt": ts, "updatedAt": ts}


@router.get("/projects/{pid}")
def get_project(pid: str):
    with db.get_db() as conn:
        r = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "项目不存在")
        stats = conn.execute(
            "SELECT COUNT(*) c, COALESCE(SUM(CASE WHEN preflight LIKE '%\"passed\":true%' THEN 1 ELSE 0 END),0) ok "
            "FROM boxes WHERE project_id=?", (pid,)).fetchone()
    return {"id": r["id"], "name": r["name"], "description": r["description"],
            "status": r["status"], "boxCount": stats["c"], "passedCount": stats["ok"],
            "createdAt": r["created_at"], "updatedAt": r["updated_at"]}


@router.put("/projects/{pid}")
def update_project(pid: str, upd: ProjectUpdate):
    with db.get_db() as conn:
        r = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "项目不存在")
        name = upd.name if upd.name is not None else r["name"]
        desc = upd.description if upd.description is not None else r["description"]
        status = upd.status if upd.status is not None else r["status"]
        ts = db.now()
        conn.execute("UPDATE projects SET name=?, description=?, status=?, updated_at=? WHERE id=?",
                     (name, desc, status, ts, pid))
    return {"id": pid, "name": name, "description": desc, "status": status,
            "updatedAt": ts}


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "项目不存在")
    return {"ok": True}
