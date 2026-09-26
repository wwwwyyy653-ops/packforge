"""AI Agent — 自然语言意图解析与工具调用编排

流程：parse_intent(提示词) → 规则+LLM 混合解析 → 生成工具调用计划(plan) → execute_plan 逐步执行。
当前实现以规则解析为主（离线可用），预留 LLM 接入点。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .engines.dieline import BOX_REGISTRY, generate, list_box_types
from .engines.packtools import (BctInput, bct_calculate, container_load,
                                cost_estimate, imposition_calculate,
                                ImpositionInput, material_db, finish_db)
from .engines.preflight import run_preflight


# 关键词 → 盒型
BOX_KEYWORDS = [
    ("扣底", "auto-lock"), ("锁底", "lock-bottom"), ("吊孔", "hanging"),
    ("翻盖", "hinged-lid"), ("铰链盖", "hinged-lid"), ("邮寄盒", "mailer"),
    ("飞机盒", "airplane"), ("天地盖", "lid-base"), ("抽屉盒", "drawer"),
    ("套筒", "sleeve"), ("手提盒", "handle"), ("展示盒", "display"),
    ("开窗盒", "window"), ("多件装", "multi"), ("双插盒", "double-tuck"),
    ("单插盒", "tuck-end"), ("纸盒", "tuck-end"), ("盒", "tuck-end"),
]

# 工艺关键词
FINISH_KEYWORDS = {
    "烫金": "foil", "击凸": "emboss", "击凹": "deboss", "哑膜": "matte",
    "光膜": "gloss", "UV": "uv", "局部UV": "spot-uv", "覆膜": "laminate",
}

# 材料关键词
MATERIAL_KEYWORDS = [
    ("白卡", "350g 白卡"), ("黑卡", "300g 黑卡"), ("牛皮纸", "250g 牛皮纸"),
    ("铜版纸", "250g 铜版纸"), ("E瓦楞", "E瓦楞"), ("B瓦楞", "B瓦楞"),
    ("C瓦楞", "C瓦楞"), ("瓦楞", "B瓦楞"),
]


def parse_dimensions(text: str) -> Optional[Dict[str, float]]:
    """提取 L×W×H 尺寸（支持 ×/x/*/空格 分隔）。"""
    text = text.replace("×", "x").replace("X", "x").replace("*", "x").replace(" ", "")
    m = re.search(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return {"length": float(m.group(1)), "width": float(m.group(2)),
            "height": float(m.group(3))}


def parse_intent(prompt: str) -> Dict[str, Any]:
    """解析用户提示词 → 意图结构。"""
    text = prompt.lower()
    intent: Dict[str, Any] = {}

    box_type = None
    for kw, bt in BOX_KEYWORDS:
        if kw in prompt:
            box_type = bt
            break
    if box_type is None:
        box_type = "tuck-end"
    intent["boxType"] = box_type

    dims = parse_dimensions(text)
    if dims:
        intent["dimensions"] = dims

    for kw, fid in FINISH_KEYWORDS.items():
        if kw in prompt:
            intent.setdefault("finishes", []).append(fid)
    if "finishes" not in intent:
        intent["finishes"] = []

    for kw, mat in MATERIAL_KEYWORDS:
        if kw in prompt:
            intent["material"] = mat
            break

    if "抗压" in prompt or "堆码" in prompt:
        intent["wantBct"] = True
    if "拼版" in prompt or "算料" in prompt or "利用率" in prompt:
        intent["wantImposition"] = True
    if "成本" in prompt or "报价" in prompt or "价格" in prompt:
        intent["wantCost"] = True
    if "装柜" in prompt or "集装箱" in prompt:
        intent["wantContainer"] = True
    return intent


def build_plan(intent: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    """由意图生成工具调用计划。"""
    steps: List[Dict[str, Any]] = []
    step_id = 0

    def add(tool: str, args: dict, summary: str, confirm: bool = False):
        nonlocal step_id
        steps.append({"index": step_id, "tool": tool, "arguments": args,
                      "summary": summary, "requiresConfirmation": confirm})
        step_id += 1

    bt = intent.get("boxType", "tuck-end")
    dims = intent.get("dimensions", {})
    add("box.search", {"query": prompt}, f"匹配盒型：{bt}")
    add("box.create", {"boxType": bt, "parameters": dims,
                        "material": intent.get("material", "350g 白卡")},
        f"创建盒型（{bt}）", confirm=not bool(dims))

    finishes = intent.get("finishes", [])
    if finishes:
        add("finish.apply", {"finishes": finishes},
            f"应用工艺：{'/'.join(finishes)}", confirm=True)

    if intent.get("wantImposition"):
        add("imposition.calculate", {"boxWidth": dims.get("length", 0),
                                     "boxHeight": dims.get("height", 0),
                                     "sheetWidth": 889, "sheetHeight": 1194},
            "拼版算料（正度对开）")
    if intent.get("wantBct"):
        add("bct.calculate", {"ect": 6800, "thickness": 3.0,
                               "length": dims.get("length", 0),
                               "width": dims.get("width", 0),
                               "stackHeight": 2000}, "抗压强度计算（B瓦楞）")
    if intent.get("wantCost"):
        add("cost.estimate", {"quantity": 1000, "areaM2": 0.15,
                               "grammage": 350, "paperPricePerKg": 7.5,
                               "finishes": finishes}, "成本估算（1000件）")
    if intent.get("wantContainer"):
        add("container.load", {"containerId": "40HQ", "boxLength": dims.get("length", 0),
                                "boxWidth": dims.get("width", 0),
                                "boxHeight": dims.get("height", 0), "boxWeightKg": 0.5},
            "装柜模拟（40HQ）")

    summary = f"创建盒型（{dims or intent.get('material', '')}）"
    if finishes:
        summary += f" + 工艺{'/'.join(finishes)}"
    return {"risk": "low" if dims else "medium", "summary": summary,
            "intent": intent, "steps": steps}


def execute_plan(plan: Dict[str, Any], approved: bool = False) -> Dict[str, Any]:
    """执行计划。confirmed=True 表示用户确认所有需确认步骤。"""
    results: List[Dict[str, Any]] = []
    box_payload = None
    intent = plan.get("intent", {})

    for step in plan.get("steps", []):
        tool = step["tool"]
        args = step.get("arguments", {})
        need_confirm = step.get("requiresConfirmation", False)
        if need_confirm and not approved:
            results.append({"step": step["index"], "tool": tool,
                            "status": "skipped", "error": "需要用户确认"})
            continue
        try:
            if tool == "box.search":
                data = {"family": args.get("query", "")[:40]}
                results.append({"step": step["index"], "tool": tool, "status": "ok", "data": data})
            elif tool == "box.create":
                bt = args.get("boxType", "tuck-end")
                params = {**args.get("parameters", {}),
                          "thickness": args.get("thickness", 0.45)}
                if not params.get("length"):
                    raise ValueError("缺少尺寸参数，无法创建盒型")
                dl = generate(bt, params)
                report = run_preflight(dl)
                box_payload = {
                    "boxType": dl.box_type, "label": dl.label,
                    "parameters": dl.parameters,
                    "flatWidth": dl.flat_width, "flatHeight": dl.flat_height,
                    "pieces": [
                        {"label": pc.label,
                         "panels": {k: {"id": v.id, "role": v.role, "name": v.name,
                                        "points": v.points, "holes": v.holes}
                                    for k, v in pc.panels.items()},
                         "folds": [{"a": f.a, "b": f.b, "angle": f.angle} for f in pc.folds]}
                        for pc in dl.pieces
                    ],
                    "panels": sum(len(pc.panels) for pc in dl.pieces),
                    "material": args.get("material", "350g 白卡"),
                    "preflight": report.to_dict(),
                }
                results.append({"step": step["index"], "tool": tool, "status": "ok", "data": box_payload})
            elif tool == "finish.apply":
                fin = args.get("finishes", [])
                cost = cost_estimate(1000, 0.15, 350, 7.5, finishes=fin)
                data = {"finishes": fin, "cost_estimate": cost}
                results.append({"step": step["index"], "tool": tool, "status": "ok", "data": data})
            elif tool == "imposition.calculate":
                res = imposition_calculate(ImpositionInput(
                    box_width=float(args.get("boxWidth", 0)),
                    box_height=float(args.get("boxHeight", 0)),
                    sheet_width=float(args.get("sheetWidth", 889)),
                    sheet_height=float(args.get("sheetHeight", 1194))))
                data = {"best": res.best.__dict__, "alternatives":
                        [a.__dict__ for a in res.alternatives]}
                results.append({"step": step["index"], "tool": tool, "status": "ok", "data": data})
            elif tool == "bct.calculate":
                res = bct_calculate(BctInput(
                    ect=float(args.get("ect", 6800)),
                    thickness=float(args.get("thickness", 3.0)),
                    length=float(args.get("length", 0)),
                    width=float(args.get("width", 0)),
                    stack_height=float(args.get("stackHeight", 2000))))
                data = res.__dict__
                results.append({"step": step["index"], "tool": tool, "status": "ok", "data": data})
            elif tool == "cost.estimate":
                res = cost_estimate(
                    int(args.get("quantity", 1000)),
                    float(args.get("areaM2", 0.15)),
                    float(args.get("grammage", 350)),
                    float(args.get("paperPricePerKg", 7.5)),
                    finishes=args.get("finishes", []))
                results.append({"step": step["index"], "tool": tool, "status": "ok", "data": res})
            elif tool == "container.load":
                res = container_load(
                    args.get("containerId", "40HQ"),
                    float(args.get("boxLength", 0)), float(args.get("boxWidth", 0)),
                    float(args.get("boxHeight", 0)), float(args.get("boxWeightKg", 0.5)))
                results.append({"step": step["index"], "tool": tool, "status": "ok", "data": res})
            else:
                results.append({"step": step["index"], "tool": tool,
                                "status": "error", "error": f"未知工具 {tool}"})
        except Exception as e:
            results.append({"step": step["index"], "tool": tool,
                            "status": "error", "error": str(e)})

    return {"results": results, "box": box_payload}
