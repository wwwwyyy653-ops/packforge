"""AI 路由：盒型目录 / 计划生成 / 计划执行 / 会话 / 配方"""
from __future__ import annotations

import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import ai_agent, database as db
from ..engines import dieline

router = APIRouter(prefix="/api/ai", tags=["ai"])


class PlanIn(BaseModel):
    prompt: str
    sessionId: Optional[str] = None


class ExecuteIn(BaseModel):
    approved: bool = True


@router.get("/box-types")
def box_types() -> dict:
    return {"boxTypes": dieline.list_box_types()}


@router.get("/tools")
def ai_tools() -> dict:
    return {"tools": [
        {"name": "box.search", "description": "按家族/关键词匹配可用盒型模板", "params": ["family"]},
        {"name": "box.create", "description": "创建参数化盒型并生成刀模", "params": ["boxType", "parameters", "material", "thickness"]},
        {"name": "finish.apply", "description": "应用印刷后道工艺", "params": ["finishes"]},
        {"name": "imposition.calculate", "description": "拼版算料利用率", "params": ["boxWidth", "boxHeight", "sheetWidth", "sheetHeight"]},
        {"name": "bct.calculate", "description": "McKee 抗压强度", "params": ["ect", "thickness", "length", "width", "stackHeight"]},
        {"name": "cost.estimate", "description": "印刷成本估算", "params": ["quantity", "areaM2", "grammage", "paperPricePerKg"]},
        {"name": "container.load", "description": "集装箱装柜模拟", "params": ["containerId", "boxLength", "boxWidth", "boxHeight"]},
    ]}


@router.post("/plan")
def create_plan(body: PlanIn) -> dict:
    plan = ai_agent.build_plan(body.prompt)
    if body.sessionId:
        ts = db.now()
        with db.get_db() as conn:
            db._insert(conn, "ai_messages", {
                "id": db.new_id("AM-"), "session_id": body.sessionId,
                "role": "user", "content": body.prompt, "created_at": ts})
            conn.execute("UPDATE ai_sessions SET updated_at=? WHERE id=?", (ts, body.sessionId))
    return plan


@router.post("/execute")
def execute(body: dict) -> dict:
    plan = body.get("plan")
    if not plan:
        raise HTTPException(400, "缺少 plan")
    approved = bool(body.get("approved", True))
    return ai_agent.execute_plan(plan, approved=approved)


@router.get("/sessions")
def sessions() -> list:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM ai_sessions ORDER BY updated_at DESC").fetchall()
        return [{"id": r["id"], "title": r["title"], "createdAt": r["created_at"],
                 "updatedAt": r["updated_at"]} for r in rows]


@router.post("/sessions")
def create_session() -> dict:
    sid = db.new_id("SES-")
    ts = db.now()
    with db.get_db() as conn:
        db._insert(conn, "ai_sessions", {"id": sid, "title": "AI 助手",
                                         "created_at": ts, "updated_at": ts})
    return {"id": sid, "title": "AI 助手", "createdAt": ts, "updatedAt": ts}


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: str) -> list:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM ai_messages WHERE session_id=? ORDER BY created_at", (session_id,)).fetchall()
        return [{"id": r["id"], "role": r["role"], "content": r["content"],
                 "createdAt": r["created_at"]} for r in rows]


class RecipeIn(BaseModel):
    name: str
    boxType: str
    parameters: dict
    material: str = "350g 白卡"
    finishes: List[str] = []
    prompt: str = ""


@router.get("/recipes")
def list_recipes() -> list:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM recipes ORDER BY created_at DESC").fetchall()
        return [{"id": r["id"], "name": r["name"], "boxType": r["box_type"],
                 "parameters": json.loads(r["parameters"]), "material": r["material"],
                 "finishes": json.loads(r["finishes"]),
                 "prompt": r["prompt"], "createdAt": r["created_at"]} for r in rows]


@router.post("/recipes")
def create_recipe(body: RecipeIn) -> dict:
    rid = db.new_id("RC-")
    ts = db.now()
    with db.get_db() as conn:
        db._insert(conn, "recipes", {
            "id": rid, "name": body.name, "box_type": body.boxType,
            "parameters": json.dumps(body.parameters, ensure_ascii=False),
            "material": body.material,
            "finishes": json.dumps(body.finishes, ensure_ascii=False),
            "prompt": body.prompt, "created_at": ts})
    return {"id": rid, "name": body.name, "createdAt": ts}


@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: str) -> dict:
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "配方不存在")
    return {"deleted": recipe_id}
