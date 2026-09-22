"""数据库层：SQLite + WAL + 迁移 + 种子数据"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

DB_PATH = os.environ.get("PACKFORGE_DB", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    status      TEXT DEFAULT 'draft',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS boxes (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    box_type    TEXT NOT NULL,
    label       TEXT NOT NULL,
    parameters  TEXT NOT NULL,
    dieline     TEXT NOT NULL,
    folding     TEXT,
    preflight   TEXT,
    thickness   REAL DEFAULT 0.45,
    material    TEXT DEFAULT '350g 白卡',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_boxes_project ON boxes(project_id);

CREATE TABLE IF NOT EXISTS tools_log (
    id          TEXT PRIMARY KEY,
    tool_type   TEXT NOT NULL,
    input       TEXT NOT NULL,
    output      TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tools_type ON tools_log(tool_type);

CREATE TABLE IF NOT EXISTS ai_sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT DEFAULT 'AI 助手',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES ai_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_session ON ai_messages(session_id);

CREATE TABLE IF NOT EXISTS box_versions (
    id          TEXT PRIMARY KEY,
    box_id      TEXT NOT NULL REFERENCES boxes(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    label       TEXT,
    parameters  TEXT NOT NULL,
    dieline     TEXT,
    material    TEXT,
    notes       TEXT DEFAULT '',
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_box_versions_box ON box_versions(box_id);

CREATE TABLE IF NOT EXISTS recipes (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    box_type    TEXT NOT NULL,
    parameters  TEXT NOT NULL,
    material    TEXT DEFAULT '350g 白卡',
    finishes    TEXT DEFAULT '[]',
    prompt      TEXT DEFAULT '',
    created_at  REAL NOT NULL
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(boxes)")}
    if "notes" not in cols:
        conn.execute("ALTER TABLE boxes ADD COLUMN notes TEXT DEFAULT ''")
    if "version" not in cols:
        conn.execute("ALTER TABLE boxes ADD COLUMN version INTEGER DEFAULT 1")
    if "tags" not in cols:
        conn.execute("ALTER TABLE boxes ADD COLUMN tags TEXT DEFAULT ''")


def now() -> float:
    return datetime.now(timezone.utc).timestamp()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _db_file() -> str:
    if DB_PATH:
        return DB_PATH
    base = Path(os.environ.get("PACKFORGE_HOME", str(Path.home() / ".packforge")))
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "packforge.db")


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_file())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
    seed_materials_and_sample()


def _insert(conn: sqlite3.Connection, table: str, data: Dict[str, Any]) -> None:
    cols = ", ".join(data.keys())
    marks = ", ".join("?" for _ in data)
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(data.values()))


def seed_materials_and_sample() -> None:
    from .engines import dieline, folding, preflight
    with get_db() as conn:
        cnt = conn.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"]
        if cnt and cnt > 0:
            return
        samples = [
            ("食品礼盒（吊孔盒）", "hanging",
             {"length": 120, "width": 80, "height": 35, "thickness": 0.45,
              "glueWidth": 15, "holeDiameter": 25}),
            ("化妆品盒（天地盖）", "lid-base",
             {"length": 90, "width": 60, "height": 40, "thickness": 0.52,
              "glueWidth": 15, "lidDepth": 32}),
            ("电子产品（飞机盒）", "airplane",
             {"length": 200, "width": 120, "height": 50, "thickness": 3.0,
              "glueWidth": 18, "wingWidth": 60}),
            ("邮寄纸箱（B瓦楞）", "mailer",
             {"length": 300, "width": 200, "height": 100, "thickness": 3.0,
              "glueWidth": 20, "flapDepth": 100}),
        ]
        ts = now()
        for name, bt, params in samples:
            pid = new_id("PRJ-")
            _insert(conn, "projects", {
                "id": pid, "name": name, "description": "示例项目",
                "status": "draft", "created_at": ts, "updated_at": ts})
            dl = dieline.generate(bt, params)
            bbox = _dieline_to_dict(dl)
            bid = new_id("BX-")
            _insert(conn, "boxes", {
                "id": bid, "project_id": pid, "box_type": bt, "label": dl.label,
                "parameters": json.dumps(params, ensure_ascii=False),
                "dieline": json.dumps(bbox, ensure_ascii=False),
                "folding": json.dumps({"tree": folding.folding_tree(dl)}, ensure_ascii=False),
                "preflight": json.dumps(preflight.run_preflight(dl).to_dict(), ensure_ascii=False),
                "thickness": float(params.get("thickness", 0.45)),
                "material": "350g 白卡",
                "created_at": ts, "updated_at": ts})


def _dieline_to_dict(dl) -> Dict:
    return {
        "boxType": dl.box_type, "label": dl.label,
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
        "notes": dl.notes, "warnings": dl.warnings,
    }
