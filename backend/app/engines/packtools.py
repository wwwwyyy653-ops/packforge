"""
PackTools — 包装行业工具箱引擎

实现 5 类计算工具（融入盒易 PackTools 能力，全部基于公开行业标准独立实现）：
1. McKee / BCT 抗压强度计算
2. 拼版算料利用率优化（正放 / 旋转90° / 混合交错）
3. 纸张克重 ↔ 厚度换算（GB/T 451.3 思路）
4. 3D 装柜排布模拟（20GP / 40GP / 40HQ）
5. 印刷成本估算（材料 / 印刷 / 后道 / 模切 / 糊盒 / 人工 / 损耗）
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 1. McKee / BCT 抗压强度
# ---------------------------------------------------------------------------
@dataclass
class BctInput:
    ect: float                 # 边压强度 (N/m)
    thickness: float           # 纸板厚度 (mm)
    length: float              # 箱长 (mm)
    width: float               # 箱宽 (mm)
    stack_height: float        # 堆码高度 (mm)
    safety_factor: float = 1.6     # 仓储周期系数
    humidity_decay: float = 0.0    # 湿度衰减 (%)

    @property
    def perimeter(self) -> float:
        return 2 * (self.length + self.width)


@dataclass
class BctResult:
    bct_n: float
    bct_kg: float
    safe_stack_count: int
    max_stack_height_mm: float
    actual_safety_factor: float
    risk_level: str            # safe / warning / critical / failed
    recommendation: str


def bct_calculate(inp: BctInput) -> BctResult:
    """McKee 公式：BCT = 5.87 × ECT × √(d × Z)"""
    ect_n_mm = inp.ect / 1000.0
    bct_base = 5.87 * ect_n_mm * math.sqrt(inp.thickness * inp.perimeter)
    humidity_factor = max(0.0, 1.0 - inp.humidity_decay / 100.0)
    bct = bct_base * humidity_factor
    bct_kg = bct / 9.81
    if bct_kg > 0:
        safe_stack = max(0, int(bct_kg / inp.safety_factor))
    else:
        safe_stack = 0
    stack_weight_kg = max(1e-9, (inp.stack_height / 1000.0) * 9.81)
    actual_sf = bct / stack_weight_kg
    if actual_sf >= inp.safety_factor * 1.5:
        risk = "safe"
        rec = "安全，可正常堆码"
    elif actual_sf >= inp.safety_factor:
        risk = "warning"
        rec = f"接近临界，建议将安全系数提升至 {inp.safety_factor * 1.2:.1f} 或降低堆码高度"
    elif actual_sf >= inp.safety_factor * 0.7:
        risk = "critical"
        rec = "有压溃风险，建议增加纸板厚度或使用更高 ECT 配材"
    else:
        risk = "failed"
        rec = f"超标！当前配材无法承受 {inp.stack_height:.0f}mm 堆码高度，必须重新配材"
    return BctResult(
        bct_n=round(bct, 2), bct_kg=round(bct_kg, 3),
        safe_stack_count=safe_stack,
        max_stack_height_mm=round(safe_stack * inp.thickness * 10, 1),
        actual_safety_factor=round(actual_sf, 2), risk_level=risk,
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# 2. 拼版算料
# ---------------------------------------------------------------------------
@dataclass
class ImpositionInput:
    box_width: float       # 成品展开宽 (mm)
    box_height: float      # 成品展开高 (mm)
    sheet_width: float     # 纸张宽 (mm)
    sheet_height: float    # 纸张高 (mm)
    trim: float = 5.0      # 修边 (mm)
    glue: float = 0.0      # 糊口附加 (mm)


@dataclass
class Layout:
    name: str
    rotation: float
    count: int
    rows: int
    columns: int
    utilization: float


@dataclass
class ImpositionResult:
    best: Layout
    alternatives: List[Layout]
    max_count: int
    utilization: float
    waste_area: float


def imposition_calculate(inp: ImpositionInput) -> ImpositionResult:
    avail_w = max(1.0, inp.sheet_width - 2 * inp.trim)
    avail_h = max(1.0, inp.sheet_height - 2 * inp.trim)
    box_w = inp.box_width + inp.glue
    box_h = inp.box_height

    layouts: List[Layout] = []

    def compute(bw: float, bh: float, rot: float, name: str) -> Layout:
        cols = max(0, int(avail_w // bw))
        rows = max(0, int(avail_h // bh))
        count = cols * rows
        used = count * bw * bh
        total = avail_w * avail_h
        return Layout(name, rot, count, rows, cols,
                      round(used / total * 100, 2) if total > 0 else 0.0)

    layouts.append(compute(box_w, box_h, 0, "正放"))
    layouts.append(compute(box_h, box_w, 90, "旋转90°"))
    mixed = _mixed_layout(avail_w, avail_h, box_w, box_h)
    if mixed:
        layouts.append(mixed)

    layouts.sort(key=lambda l: (l.count, l.utilization), reverse=True)
    best = layouts[0]
    total_area = avail_w * avail_h
    return ImpositionResult(
        best=best, alternatives=layouts[1:], max_count=best.count,
        utilization=best.utilization,
        waste_area=round(total_area * (1 - best.utilization / 100.0), 2),
    )


def _mixed_layout(avail_w: float, avail_h: float, box_w: float,
                  box_h: float) -> Optional[Layout]:
    """交替旋转的简单混合排布。"""
    if box_w <= 0 or box_h <= 0:
        return None
    x, y = 0.0, 0.0
    count = 0
    row_h = 0.0
    while y + min(box_h, box_w) <= avail_h + 1e-6:
        xx, row_h = x, 0.0
        rot = count % 2 == 0
        while True:
            w, h = (box_w, box_h) if rot else (box_h, box_w)
            if xx + w > avail_w + 1e-6:
                break
            count += 1
            row_h = max(row_h, h)
            xx += w
            rot = not rot
        if count == 0:
            break
        y += row_h
        if y > avail_h + 1e-6:
            break
    if count == 0:
        return None
    used = count * box_w * box_h
    total = avail_w * avail_h
    return Layout("混合交错", 45.0, count, 0, 0,
                  round(used / total * 100, 2) if total > 0 else 0.0)


# ---------------------------------------------------------------------------
# 3. 纸张克重 ↔ 厚度换算
# ---------------------------------------------------------------------------
PAPER_TYPES: Dict[str, dict] = {
    "white-card":  {"label": "白卡纸", "density": 0.80},
    "black-card":  {"label": "黑卡纸", "density": 0.85},
    "kraft":       {"label": "牛皮纸", "density": 0.70},
    "coated":      {"label": "铜版纸", "density": 1.05},
    "recycled":    {"label": "再生纸", "density": 0.75},
    "specialty":   {"label": "特种纸", "density": 0.90},
}


def paper_convert(value: float, paper_type: str,
                  direction: str = "g2t") -> dict:
    """direction: g2t 克重→厚度 / t2g 厚度→克重。value 单位 g/m² 或 mm。"""
    ptype = PAPER_TYPES.get(paper_type, PAPER_TYPES["white-card"])
    density = ptype["density"]
    if direction == "g2t":
        gsm = max(1e-9, value)
        thick_mm = gsm / (density * 1000.0)
    else:
        thick_mm = max(1e-9, value)
        gsm = thick_mm * density * 1000.0
    return {
        "grammage": round(gsm, 2),
        "thickness_mm": round(thick_mm, 4),
        "thickness_um": round(thick_mm * 1000, 1),
        "thickness_pt": round(thick_mm * 2.8346, 2),
        "bulk": round(1 / density, 3),
        "paper_type": paper_type,
        "paper_label": ptype["label"],
    }


# ---------------------------------------------------------------------------
# 4. 装柜排布模拟
# ---------------------------------------------------------------------------
CONTAINERS: Dict[str, dict] = {
    "20GP": {"name": "20尺标准柜", "inner_length": 5898, "inner_width": 2352,
             "inner_height": 2393, "max_payload_kg": 28200, "volume_m3": 33.2},
    "40GP": {"name": "40尺标准柜", "inner_length": 12032, "inner_width": 2352,
             "inner_height": 2393, "max_payload_kg": 26700, "volume_m3": 67.7},
    "40HQ": {"name": "40尺高柜", "inner_length": 12032, "inner_width": 2352,
             "inner_height": 2698, "max_payload_kg": 26500, "volume_m3": 76.3},
}


def container_load(container_id: str, box_length: float, box_width: float,
                   box_height: float, box_weight_kg: float) -> dict:
    c = CONTAINERS.get(container_id, CONTAINERS["20GP"])
    dims = [
        ("L×W×H", box_length, box_width, box_height),
        ("L×H×W", box_length, box_height, box_width),
        ("W×L×H", box_width, box_length, box_height),
        ("W×H×L", box_width, box_height, box_length),
        ("H×L×W", box_height, box_length, box_width),
        ("H×W×L", box_height, box_width, box_length),
    ]
    results = []
    best = None
    for name, l, w, h in dims:
        cols = max(0, int(c["inner_length"] // l))
        rows = max(0, int(c["inner_width"] // w))
        layers = max(0, int(c["inner_height"] // h))
        count = cols * rows * layers
        used_vol = count * l * w * h / 1e9
        utilization = used_vol / c["volume_m3"] * 100
        results.append({"orientation": name, "count": count,
                        "utilization": round(utilization, 2),
                        "columns": cols, "rows": rows, "layers": layers})
        if best is None or (count, utilization) > (best["count"], best["utilization"]):
            best = results[-1]
    total_weight = best["count"] * box_weight_kg
    return {
        "container": container_id,
        "container_name": c["name"],
        "inner": [c["inner_length"], c["inner_width"], c["inner_height"]],
        "volume_m3": c["volume_m3"],
        "max_payload_kg": c["max_payload_kg"],
        "best": best,
        "alternatives": results,
        "total_boxes": best["count"],
        "total_weight_kg": round(total_weight, 2),
        "weight_ok": total_weight <= c["max_payload_kg"],
    }


# ---------------------------------------------------------------------------
# 5. 印刷成本估算
# ---------------------------------------------------------------------------
FINISH_PRICES: Dict[str, float] = {  # 元/m²
    "matte": 0.8, "gloss": 0.8, "uv": 2.5, "foil": 3.5,
    "emboss": 2.0, "deboss": 2.0, "spot-uv": 3.0, "laminate": 1.2,
}
PRINT_PRICE = {"offset": (2.5, 0.5), "digital": (5.0, 0.3), "flexo": (1.8, 0.4)}


def cost_estimate(quantity: int, area_m2: float, grammage: float,
                  paper_price_per_kg: float, colors: int = 4,
                  print_type: str = "offset",
                  finishes: Optional[List[str]] = None,
                  diecut_setup: float = 300.0, profit_rate: float = 0.25) -> dict:
    qty = max(1, quantity)
    waste_rate = 0.05
    finishes = finishes or []

    weight_per_unit = area_m2 * grammage / 1000.0   # kg
    material_cost = weight_per_unit * paper_price_per_kg * qty

    base, per_color = PRINT_PRICE.get(print_type, PRINT_PRICE["offset"])
    print_cost = area_m2 * (base + colors * per_color) * qty

    finish_cost = sum(FINISH_PRICES.get(f, 1.0) * area_m2 * qty for f in finishes)

    diecut_cost = diecut_setup / qty + 0.05 * area_m2 * qty

    glue_cost = 0.02 * qty

    labor_cost = 80.0 * (qty / 2000.0)

    subtotal = material_cost + print_cost + finish_cost + diecut_cost + glue_cost + labor_cost
    waste_cost = subtotal * waste_rate
    total_cost = subtotal + waste_cost
    unit_cost = total_cost / qty
    suggested_price = unit_cost * (1 + profit_rate)

    return {
        "quantity": qty,
        "material_cost": round(material_cost, 2),
        "print_cost": round(print_cost, 2),
        "finish_cost": round(finish_cost, 2),
        "diecut_cost": round(diecut_cost, 2),
        "glue_cost": round(glue_cost, 2),
        "labor_cost": round(labor_cost, 2),
        "waste_cost": round(waste_cost, 2),
        "total_cost": round(total_cost, 2),
        "unit_cost": round(unit_cost, 4),
        "suggested_price": round(suggested_price, 4),
        "profit_rate": profit_rate,
    }


def material_db() -> List[dict]:
    """常用纸板材质库（克重/厚度/中性层系数）。"""
    return [
        {"id": "white-300", "name": "300g 白卡", "thickness": 0.35, "grammage": 300,
         "neutral": 0.50, "category": "白卡"},
        {"id": "white-350", "name": "350g 白卡", "thickness": 0.45, "grammage": 350,
         "neutral": 0.50, "category": "白卡"},
        {"id": "white-400", "name": "400g 白卡", "thickness": 0.52, "grammage": 400,
         "neutral": 0.50, "category": "白卡"},
        {"id": "black-300", "name": "300g 黑卡", "thickness": 0.38, "grammage": 300,
         "neutral": 0.50, "category": "黑卡"},
        {"id": "kraft-250", "name": "250g 牛皮纸", "thickness": 0.36, "grammage": 250,
         "neutral": 0.50, "category": "牛皮纸"},
        {"id": "coated-250", "name": "250g 铜版纸", "thickness": 0.24, "grammage": 250,
         "neutral": 0.50, "category": "铜版纸"},
        {"id": "e-flute", "name": "E瓦楞", "thickness": 1.5, "grammage": None,
         "neutral": 0.35, "category": "瓦楞"},
        {"id": "b-flute", "name": "B瓦楞", "thickness": 3.0, "grammage": None,
         "neutral": 0.30, "category": "瓦楞"},
        {"id": "c-flute", "name": "C瓦楞", "thickness": 4.0, "grammage": None,
         "neutral": 0.28, "category": "瓦楞"},
        {"id": "eb-flute", "name": "EB瓦楞", "thickness": 4.5, "grammage": None,
         "neutral": 0.32, "category": "瓦楞"},
    ]


def finish_db() -> List[dict]:
    return [
        {"id": "matte", "name": "哑膜", "price_per_m2": 0.8},
        {"id": "gloss", "name": "光膜", "price_per_m2": 0.8},
        {"id": "uv", "name": "UV 上光", "price_per_m2": 2.5},
        {"id": "spot-uv", "name": "局部 UV", "price_per_m2": 3.0},
        {"id": "foil", "name": "烫金", "price_per_m2": 3.5},
        {"id": "emboss", "name": "击凸", "price_per_m2": 2.0},
        {"id": "deboss", "name": "击凹", "price_per_m2": 2.0},
        {"id": "laminate", "name": "覆膜", "price_per_m2": 1.2},
    ]
