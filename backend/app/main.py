"""包装参数化设计软件 — FastAPI 入口"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database as db
from .routers import ai, boxes, export, projects, tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="包装参数化设计软件 API",
    description="15 种盒型参数化刀模引擎 / PackTools 工具箱 / 预检 / 导出 / AI Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(boxes.router)
app.include_router(tools.router)
app.include_router(export.router)
app.include_router(ai.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "1.0.0",
            "boxTypes": len([1]) and __box_count()}


def __box_count() -> int:
    from .engines.dieline import BOX_REGISTRY
    return len(BOX_REGISTRY)


@app.get("/")
def root() -> dict:
    return {"name": "包装参数化设计软件", "docs": "/docs", "health": "/api/health"}
