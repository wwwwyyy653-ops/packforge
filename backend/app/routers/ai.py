"""AI 路由：计划解析 / 执行 / 配方管理 / 工具库"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import database as db
from ..ai_agent import build_plan, execute_plan, list_box_types, parse_intent
from ..engines.packtools import finish_db, material_db

router = APIRouter(prefix="/api/ai", tags=["AI"])


class PlanRequest(BaseModel):
    prompt: str


class ExecuteRequest(BaseModel):
    plan: dict
    approved: bool = False


class RecipeIn(BaseModel):
    name: str
    box_type: str
    parameters: dict = {}
    material: str = "350g 白卡"
    finishes: List[str] = []
    prompt: str = ""


@router.post("/plan")
def ai_plan(req: PlanRequest):
    """解析提示词 → 执行计划。"""
    intent = parse_intent(req.prompt)
    plan = build_plan(intent, req.prompt)
    return plan


@router.post("/execute")
def ai_execute(req: ExecuteRequest):
    """执行计划。"""
    result = execute_plan(req.plan, req.approved)
    return result


@router.get("/box-types")
def box_types():
    return list_box_types()


@router.get("/materials")
def materials():
    return material_db()


@router.get("/finishes")
def finishes():
    return finish_db()


@router.get("/recipes")
def list_recipes():
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM recipes ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        out.append({"id": r["id"], "name": r["name"], "boxType": r["box_type"],
                    "parameters": json.loads(r["parameters"]),
                    "material": r["material"],
                    "finishes": json.loads(r["finishes"] or "[]"),
                    "prompt": r["prompt"], "createdAt": r["created_at"]})
    return out


@router.post("/recipes")
def create_recipe(recipe: RecipeIn):
    rid = db.new_id("RCP-")
    ts = db.now()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO recipes (id, name, box_type, parameters, material, finishes, prompt, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (rid, recipe.name, recipe.box_type,
             json.dumps(recipe.parameters, ensure_ascii=False),
             recipe.material, json.dumps(recipe.finishes, ensure_ascii=False),
             recipe.prompt, ts))
    return {"id": rid, "name": recipe.name}


@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: str):
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "配方不存在")
    return {"ok": True}
