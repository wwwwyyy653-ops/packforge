"""
Packaging Engine — 参数化盒型刀模引擎

实现 15 种常用包装盒型的参数化 2D 刀模生成：
扣底盒 / 双插盒 / 单插盒 / 锁底盒 / 吊孔盒 / 翻盖盒 / 邮寄盒 / 飞机盒
天地盖 / 抽屉盒 / 套筒 / 手提盒 / 展示盒 / 开窗盒 / 多件装

坐标约定：mm，Y 轴向上。每块面板为闭合多边形（外轮廓顺时针），孔洞为独立多边形。
所有面板拼接后即为完整刀模图（切割线=外轮廓，折痕线=面板共享边）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .geometry import (Point, Polygon, Rect, circle_points, polygon_area,
                       polygon_bbox, rect_poly, shared_edge, simplify_axis,
                       slot_points)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
@dataclass
class PanelSpec:
    """一块面板（实体区域）"""
    id: str
    role: str                 # front/back/left/right/top-flap/bottom-flap/tuck/dust/glue/lid/base/divider/handle/wing/lock
    name: str
    points: Polygon           # 外轮廓（顺时针）
    holes: List[Polygon] = field(default_factory=list)   # 孔洞（逆时针）
    extra: Dict = field(default_factory=dict)


@dataclass
class FoldSpec:
    """折叠关系（折痕）：a 与 b 共享一条边，折叠角 angle（度）"""
    a: str
    b: str
    angle: float


@dataclass
class DielinePiece:
    """一片刀模（整体或天地盖的一部分）"""
    label: str
    panels: Dict[str, PanelSpec]
    folds: List[FoldSpec]


@dataclass
class DielineData:
    box_type: str
    label: str
    parameters: dict
    pieces: List[DielinePiece]
    flat_width: float = 0.0          # 整体展开尺寸（全部拼合）
    flat_height: float = 0.0
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def two_piece(self) -> bool:
        return len(self.pieces) > 1

    @property
    def all_panels(self) -> Dict[str, PanelSpec]:
        out: Dict[str, PanelSpec] = {}
        for pc in self.pieces:
            for k, v in pc.panels.items():
                out[f"{pc.label}:{k}" if self.two_piece else k] = v
        return out

    @property
    def all_folds(self) -> List[FoldSpec]:
        if not self.two_piece:
            return self.pieces[0].folds
        return [FoldSpec(f"{pc.label}:{f.a}", f"{pc.label}:{f.b}", f.angle)
                for pc in self.pieces for f in pc.folds]


# ---------------------------------------------------------------------------
# 布局辅助
# ---------------------------------------------------------------------------
def _row_x(panels: List[Tuple[str, str, float, float]], gap: float = 0.0
           ) -> Dict[str, Polygon]:
    """把一组 (id, role, w, h) 按行从左到右排列（y=0..h），返回 id->多边形。"""
    out: Dict[str, Polygon] = {}
    x = 0.0
    for pid, _role, w, h in panels:
        out[pid] = rect_poly(x, 0.0, w, h)
        x += w + gap
    return out


def _flap_top(panel: Polygon, depth: float) -> Polygon:
    """面板顶部的外翻片（向上，y 增大方向）。panel 为矩形(顺时针)。"""
    x0, y0 = panel[0]
    x1, _ = panel[1]
    y1 = panel[2][1]
    return [(x0, y1), (x1, y1), (x1, y1 + depth), (x0, y1 + depth)]


def _flap_bottom(panel: Polygon, depth: float) -> Polygon:
    x0, y0 = panel[0]
    x1, _ = panel[1]
    return [(x0, y0), (x1, y0), (x1, y0 - depth), (x0, y0 - depth)]


def _flap_left(panel: Polygon, depth: float) -> Polygon:
    x0, y0 = panel[0]
    _, y1 = panel[2][1] if False else panel[2]
    y1 = panel[2][1]
    return [(x0, y0), (x0 - depth, y0), (x0 - depth, y1), (x0, y1)]


def _flap_right(panel: Polygon, depth: float) -> Polygon:
    x0, y0 = panel[0]
    x1 = panel[1][0]
    y1 = panel[2][1]
    return [(x1, y0), (x1 + depth, y0), (x1 + depth, y1), (x1, y1)]


def _panel_bbox(poly: Polygon) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _auto_folds(pieces: List[DielinePiece]) -> None:
    """自动在共享边的面板之间生成折痕（默认 90°）。"""
    for pc in pieces:
        ids = list(pc.panels.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                e = shared_edge(pc.panels[a].points, pc.panels[b].points)
                if e is not None:
                    pc.folds.append(FoldSpec(a, b, 90.0))


def _finalize(dieline: DielineData, margin: float = 15.0) -> DielineData:
    """计算整体展开尺寸并清理。"""
    xs0 = ys0 = 1e18
    xs1 = ys1 = -1e18
    for pc in dieline.pieces:
        for p in pc.panels.values():
            for pt in p.points:
                xs0 = min(xs0, pt[0]); ys0 = min(ys0, pt[1])
                xs1 = max(xs1, pt[0]); ys1 = max(ys1, pt[1])
    dieline.flat_width = round(xs1 - xs0, 3)
    dieline.flat_height = round(ys1 - ys0, 3)
    return dieline


# ---------------------------------------------------------------------------
# 各盒型生成器
# ---------------------------------------------------------------------------
def _params(P: dict, *keys: str, defaults: dict = None) -> dict:
    d = defaults or {}
    return {k: float(P.get(k, d.get(k, 0))) for k in keys}


# 1) 单插盒 ---------------------------------------------------------------
def gen_tuck_end(P: dict, with_dust: bool = False) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    tuck = float(P.get("tuckDepth", W * 0.5))          # 插舌深
    dust = float(P.get("dustFlap", W * 0.5))           # 防尘翼深
    d = P.get("tuckDepth") is None

    panels: Dict[str, PanelSpec] = {}
    row = _row_x([("glue", "glue", glue, H),
                  ("front", "front", L, H),
                  ("right", "right", W, H),
                  ("back", "back", L, H),
                  ("left", "left", W, H)])
    for pid in ("front", "back"):
        for tag, depth in (("t", tuck), ("b", tuck)):
            poly = _flap_top(row[pid], depth) if tag == "t" else _flap_bottom(row[pid], depth)
            panels[f"{pid}-{tag}flap"] = PanelSpec(f"{pid}-{tag}flap", "tuck",
                                                   f"{'顶部' if tag=='t' else '底部'}插舌",
                                                   poly)
    if with_dust:
        for pid in ("left", "right"):
            for tag in ("t", "b"):
                poly = _flap_top(row[pid], dust) if tag == "t" else _flap_bottom(row[pid], dust)
                panels[f"{pid}-{tag}dust"] = PanelSpec(f"{pid}-{tag}dust", "dust",
                                                       f"{'顶部' if tag=='t' else '底部'}防尘翼",
                                                       poly)
    panels["glue"] = PanelSpec("glue", "glue", "糊头", row["glue"])
    panels["front"] = PanelSpec("front", "front", "前面板", row["front"])
    panels["right"] = PanelSpec("right", "right", "右侧板", row["right"])
    panels["back"] = PanelSpec("back", "back", "后面板", row["back"])
    panels["left"] = PanelSpec("left", "left", "左侧板", row["left"])

    folds: List[FoldSpec] = []
    for a, b, ang in [("front", "right", 90), ("right", "back", 90),
                      ("back", "left", 90), ("left", "glue", 180)]:
        folds.append(FoldSpec(a, b, ang))
    for pid in ("front", "back"):
        folds.append(FoldSpec(pid, f"{pid}-tflap", 90))
        folds.append(FoldSpec(pid, f"{pid}-bflap", 90))
        folds.append(FoldSpec(f"{pid}-tflap", f"{pid}-tflap2", 0))  # 占位忽略
    for pid in ("front", "back"):
        folds = [f for f in folds if not f.a.endswith("flap2")]
    for pid in ("front", "back"):
        folds.append(FoldSpec(f"{pid}-tflap", f"{pid}-ttuck", 180))
        folds.append(FoldSpec(f"{pid}-bflap", f"{pid}-btuck", 180))
        panels[f"{pid}-ttuck"] = panels.pop(f"{pid}-tflap")
        panels[f"{pid}-btuck"] = panels.pop(f"{pid}-bflap")
    panels2: Dict[str, PanelSpec] = {}
    folds2: List[FoldSpec] = []
    for pid, spec in panels.items():
        if pid.endswith("ttuck") or pid.endswith("btuck"):
            base = pid.split("-")[0]
            is_t = pid.endswith("ttuck")
            folds2.append(FoldSpec(base, pid, 180))
        panels2[pid] = spec
    folds2.extend(f for f in folds if f.a in panels2 and f.b in panels2)
    if with_dust:
        for pid in ("left", "right"):
            for tag in ("t", "b"):
                folds2.append(FoldSpec(pid, f"{pid}-{tag}dust", 90))
    piece = DielinePiece("主体", panels2, folds2)
    dl = DielineData("tuck-end", "单插盒", dict(P), [piece])
    return _finalize(dl)


# 2) 双插盒（同单插盒 + 防尘翼） -------------------------------------------
def gen_double_tuck(P: dict) -> DielineData:
    return gen_tuck_end(P, with_dust=True)


# 3) 吊孔盒 ---------------------------------------------------------------
def gen_hanging(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    tuck = float(P.get("tuckDepth", W * 0.5))
    hole_d = float(P.get("holeDiameter", 25))
    hang_h = float(P.get("hangTabHeight", 25))

    dl = gen_tuck_end({**P, "tuckDepth": tuck})
    pc = dl.pieces[0]
    front_flap = pc.panels.get("front-tflap") or pc.panels.get("front-ttuck")
    if front_flap:
        bx0, by0, bx1, by1 = _panel_bbox(front_flap.points)
        cx = (bx0 + bx1) / 2
        cy = by1 - hang_h * 0.5
        front_flap.holes.append(circle_points(cx, cy, hole_d / 2))
    dl.box_type = "hanging"
    dl.label = "吊孔盒"
    return dl


# 4) 扣底盒（自动锁底） ---------------------------------------------------
def gen_auto_lock(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    tuck = float(P.get("tabDepth", W * 0.5))
    lock_w = float(P.get("lockWidth", W * 0.35))

    panels: Dict[str, PanelSpec] = {}
    row = _row_x([("glue", "glue", glue, H),
                  ("front", "front", L, H),
                  ("right", "right", W, H),
                  ("back", "back", L, H),
                  ("left", "left", W, H)])
    for pid in ("front", "back"):
        panels[f"{pid}-tflap"] = PanelSpec(f"{pid}-tflap", "tuck", "顶部插舌",
                                           _flap_top(row[pid], tuck))
        panels[f"{pid}-bflap"] = PanelSpec(f"{pid}-bflap", "lock", "底部锁底翼",
                                           _flap_bottom(row[pid], tuck))
    for pid, sign in (("left", 1), ("right", -1)):
        poly = row[pid]
        x0, y0, x1, y1 = _panel_bbox(poly)
        wing_h = W * 0.28
        if sign > 0:
            lock = [(x0, y0), (x1, y0), (x1 - lock_w, y0 - wing_h), (x0, y0 - wing_h)]
        else:
            lock = [(x0, y0), (x1, y0), (x1, y0 - wing_h), (x0 + lock_w, y0 - wing_h)]
        panels[f"{pid}-lock"] = PanelSpec(f"{pid}-lock", "lock", "锁底翼", lock)
    for k, v in [("glue", "糊头"), ("front", "前面板"), ("right", "右侧板"),
                 ("back", "后面板"), ("left", "左侧板")]:
        panels[k] = PanelSpec(k, k, v, row[k])

    folds: List[FoldSpec] = []
    for a, b, ang in [("front", "right", 90), ("right", "back", 90),
                      ("back", "left", 90), ("left", "glue", 180)]:
        folds.append(FoldSpec(a, b, ang))
    for pid in ("front", "back"):
        folds.append(FoldSpec(pid, f"{pid}-tflap", 90))
        folds.append(FoldSpec(pid, f"{pid}-bflap", 90))
    for pid in ("left", "right"):
        folds.append(FoldSpec(pid, f"{pid}-lock", 90))
    piece = DielinePiece("主体", panels, folds)
    dl = DielineData("auto-lock", "扣底盒（自动锁底）", dict(P), [piece])
    return _finalize(dl)


# 5) 锁底盒 ---------------------------------------------------------------
def gen_lock_bottom(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    lock_d = float(P.get("lockDepth", W * 0.3))

    dl = gen_auto_lock(P)
    pc = dl.pieces[0]
    for pid in ("front", "back"):
        if f"{pid}-bflap" in pc.panels:
            pc.panels[f"{pid}-bflap"].role = "lock"
            pc.panels[f"{pid}-bflap"].name = "底部锁底插舌"
    dl.box_type = "lock-bottom"
    dl.label = "锁底盒"
    return dl


# 6) 翻盖盒（铰链盖，0301 风格单件） -------------------------------------
def gen_hinged_lid(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    lid_h = float(P.get("lidHeight", H * 0.6))

    panels: Dict[str, PanelSpec] = {}
    x0 = 0.0
    back = rect_poly(x0, 0, L, H)
    lid_back = rect_poly(x0, H, L, lid_h)
    lid_top = rect_poly(x0, H + lid_h, L, W)
    lid_front = rect_poly(x0, H + lid_h + W, L, lid_h * 0.5)
    left = rect_poly(-W - glue, 0, W, H)
    right = rect_poly(L + glue, 0, W, H)
    lid_left = [(x0 - W - glue, H + lid_h), (x0 - glue, H + lid_h),
                (x0 - glue, H + lid_h + lid_h * 0.5), (x0 - W - glue, H + lid_h + lid_h * 0.5)]
    lid_right = [(x0 + L + glue, H + lid_h), (x0 + L + glue + W, H + lid_h),
                 (x0 + L + glue + W, H + lid_h + lid_h * 0.5),
                 (x0 + L + glue, H + lid_h + lid_h * 0.5)]
    front = rect_poly(x0, -H, L, H)
    bottom_flap = _flap_bottom(front, W * 0.5)

    panels["back"] = PanelSpec("back", "back", "后壁（铰链）", back)
    panels["lid-back"] = PanelSpec("lid-back", "lid", "盖后壁", lid_back)
    panels["lid-top"] = PanelSpec("lid-top", "lid", "盖顶", lid_top)
    panels["lid-front"] = PanelSpec("lid-front", "lid", "盖前片", lid_front)
    panels["left"] = PanelSpec("left", "left", "左壁", left)
    panels["right"] = PanelSpec("right", "right", "右壁", right)
    panels["lid-left"] = PanelSpec("lid-left", "lid", "盖左翼", lid_left)
    panels["lid-right"] = PanelSpec("lid-right", "lid", "盖右翼", lid_right)
    panels["front"] = PanelSpec("front", "front", "前壁", front)
    panels["bottom"] = PanelSpec("bottom", "bottom", "底盖", bottom_flap)

    folds: List[FoldSpec] = [
        FoldSpec("back", "left", 90), FoldSpec("back", "right", 90),
        FoldSpec("back", "front", 90), FoldSpec("front", "bottom", 90),
        FoldSpec("back", "lid-back", 90),
        FoldSpec("lid-back", "lid-top", 90),
        FoldSpec("lid-top", "lid-front", 90),
        FoldSpec("lid-top", "lid-left", 90),
        FoldSpec("lid-top", "lid-right", 90),
    ]
    piece = DielinePiece("主体", panels, folds)
    dl = DielineData("hinged-lid", "翻盖盒（铰链盖）", dict(P), [piece])
    return _finalize(dl)


# 7) 邮寄盒（0427）--------------------------------------------------------
def gen_mailer(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    flap_d = float(P.get("flapDepth", W * 0.5))
    tear = P.get("tearStrip", 0)

    panels: Dict[str, PanelSpec] = {}
    row = _row_x([("glue", "glue", glue, H),
                  ("front", "front", L, H),
                  ("right", "right", W, H),
                  ("back", "back", L, H),
                  ("left", "left", W, H)])
    for pid in ("front", "back"):
        panels[f"{pid}-tflap"] = PanelSpec(f"{pid}-tflap", "tuck", "顶部盖片",
                                           _flap_top(row[pid], flap_d))
        panels[f"{pid}-bflap"] = PanelSpec(f"{pid}-bflap", "tuck", "底部盖片",
                                           _flap_bottom(row[pid], flap_d))
    for pid in ("left", "right"):
        panels[f"{pid}-tdust"] = PanelSpec(f"{pid}-tdust", "dust", "顶部防尘翼",
                                           _flap_top(row[pid], flap_d * 0.6))
        panels[f"{pid}-bdust"] = PanelSpec(f"{pid}-bdust", "dust", "底部防尘翼",
                                           _flap_bottom(row[pid], flap_d * 0.6))
    if tear > 0:
        fx0, fy0, fx1, fy1 = _panel_bbox(row["front"])
        y = fy0 + min(H * 0.3, tear)
        panels["front"].extra["tearStrip"] = [(fx0 + 5, y), (fx1 - 5, y)]
    for k, v in [("glue", "糊头"), ("front", "前面板"), ("right", "右侧板"),
                 ("back", "后面板"), ("left", "左侧板")]:
        panels[k] = PanelSpec(k, k, v, row[k])

    folds: List[FoldSpec] = []
    for a, b, ang in [("front", "right", 90), ("right", "back", 90),
                      ("back", "left", 90), ("left", "glue", 180)]:
        folds.append(FoldSpec(a, b, ang))
    for pid in ("front", "back"):
        folds.append(FoldSpec(pid, f"{pid}-tflap", 90))
        folds.append(FoldSpec(pid, f"{pid}-bflap", 90))
    for pid in ("left", "right"):
        folds.append(FoldSpec(pid, f"{pid}-tdust", 90))
        folds.append(FoldSpec(pid, f"{pid}-bdust", 90))
    piece = DielinePiece("主体", panels, folds)
    dl = DielineData("mailer", "邮寄盒", dict(P), [piece])
    return _finalize(dl)


# 8) 飞机盒（0422 单件飞机盒）--------------------------------------------
def gen_airplane(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    wing = float(P.get("wingWidth", W * 0.5))
    tuck = float(P.get("tuckDepth", W * 0.35))

    panels: Dict[str, PanelSpec] = {}
    row = _row_x([("glue", "glue", glue, H),
                  ("front", "front", L, H),
                  ("right", "right", W, H),
                  ("back", "back", L, H),
                  ("left", "left", W, H)])
    top_lid = _flap_top(row["front"], wing)
    tuck_flap = _flap_top([(top_lid[0][0], top_lid[2][1]), (top_lid[1][0], top_lid[2][1]),
                           (top_lid[1][0], top_lid[2][1] + tuck), (top_lid[0][0], top_lid[2][1] + tuck)],
                          tuck)
    lw = _flap_top(row["left"], wing)
    rw = _flap_top(row["right"], wing)
    b_lid = _flap_bottom(row["front"], wing)
    b_tuck = _flap_bottom([(b_lid[0][0], b_lid[2][1]), (b_lid[1][0], b_lid[2][1]),
                           (b_lid[1][0], b_lid[2][1] - tuck), (b_lid[0][0], b_lid[2][1] - tuck)], tuck)

    panels["top-lid"] = PanelSpec("top-lid", "lid", "顶盖", top_lid)
    panels["top-tuck"] = PanelSpec("top-tuck", "tuck", "顶盖插舌", tuck_flap)
    panels["bottom-lid"] = PanelSpec("bottom-lid", "lid", "底盖", b_lid)
    panels["bottom-tuck"] = PanelSpec("bottom-tuck", "tuck", "底盖插舌", b_tuck)
    panels["left-wing"] = PanelSpec("left-wing", "wing", "左翼", lw)
    panels["right-wing"] = PanelSpec("right-wing", "wing", "右翼", rw)
    for k, v in [("glue", "糊头"), ("front", "前面板"), ("right", "右侧板"),
                 ("back", "后面板"), ("left", "左侧板")]:
        panels[k] = PanelSpec(k, k, v, row[k])

    folds: List[FoldSpec] = [
        FoldSpec("front", "right", 90), FoldSpec("right", "back", 90),
        FoldSpec("back", "left", 90), FoldSpec("left", "glue", 180),
        FoldSpec("front", "top-lid", 90), FoldSpec("top-lid", "top-tuck", 180),
        FoldSpec("front", "bottom-lid", 90), FoldSpec("bottom-lid", "bottom-tuck", 180),
        FoldSpec("left", "left-wing", 90), FoldSpec("right", "right-wing", 90),
    ]
    piece = DielinePiece("主体", panels, folds)
    dl = DielineData("airplane", "飞机盒", dict(P), [piece])
    return _finalize(dl)


# 9) 天地盖（0300 两件套）-------------------------------------------------
def _tray_piece(L: float, W: float, H: float, t: float, label: str,
                glue: float) -> DielinePiece:
    """十字形浅盘：底 + 四壁 + 角糊片（简化为壁侧糊片）。"""
    panels: Dict[str, PanelSpec] = {}
    bottom = rect_poly(0, 0, L, W)
    front = rect_poly(0, W, L, H)          # 上
    back = rect_poly(0, -H, L, H)          # 下
    left = rect_poly(-H, 0, H, W)          # 左
    right = rect_poly(L, 0, H, W)          # 右
    panels["bottom"] = PanelSpec("bottom", "base", "底板", bottom)
    panels["front"] = PanelSpec("front", "wall", "前壁", front)
    panels["back"] = PanelSpec("back", "wall", "后壁", back)
    panels["left"] = PanelSpec("left", "wall", "左壁", left)
    panels["right"] = PanelSpec("right", "wall", "右壁", right)
    folds = [FoldSpec("bottom", "front", 90), FoldSpec("bottom", "back", 90),
             FoldSpec("bottom", "left", 90), FoldSpec("bottom", "right", 90)]
    return DielinePiece(label, panels, folds)


def gen_lid_base(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    lid_d = float(P.get("lidDepth", H * 0.8))
    gap = float(P.get("gapTolerance", 0.5))

    base = _tray_piece(L, W, H, t, "盒身", glue)
    lid = _tray_piece(L + 2 * t + 2 * gap, W + 2 * t + 2 * gap, lid_d, t, "盒盖", glue)
    max_base = max(p[1] for pc in [base] for p in pc.panels["front"].points)
    for spec in lid.panels.values():
        spec.points = [(x, y + max_base + 40) for x, y in spec.points]
    dl = DielineData("lid-base", "天地盖", dict(P), [base, lid])
    return _finalize(dl)


# 10) 抽屉盒（0903/0904 套+屉）-------------------------------------------
def gen_drawer(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    tray_d = float(P.get("trayDepth", H * 0.5))
    gap = float(P.get("sleeveGap", 0.5))

    sleeve: Dict[str, PanelSpec] = {}
    sL, sW = L + 2 * gap, W + 2 * gap
    row = _row_x([("glue", "glue", glue, sW),
                  ("s-front", "sleeve", sL, sW),
                  ("s-right", "sleeve", sL, sW)])
    row = _row_x([("glue", "glue", glue, sW),
                  ("s-front", "sleeve", sL, sW),
                  ("s-right", "sleeve", sW, sW),
                  ("s-back", "sleeve", sL, sW),
                  ("s-left", "sleeve", sW, sW)])
    for k, v in [("glue", "糊头"), ("s-front", "套前"), ("s-right", "套右"),
                 ("s-back", "套后"), ("s-left", "套左")]:
        sleeve[k] = PanelSpec(k, k, v, row[k])
    folds_s = [FoldSpec("s-front", "s-right", 90), FoldSpec("s-right", "s-back", 90),
               FoldSpec("s-back", "s-left", 90), FoldSpec("s-left", "glue", 180)]

    tray: Dict[str, PanelSpec] = {}
    tL, tW = L, W
    row2 = _row_x([("glue2", "glue", glue, tray_d),
                   ("t-front", "tray", tL, tray_d),
                   ("t-right", "tray", tW, tray_d),
                   ("t-back", "tray", tL, tray_d),
                   ("t-left", "tray", tW, tray_d)])
    for k, v in [("glue2", "糊头"), ("t-front", "屉前"), ("t-right", "屉右"),
                 ("t-back", "屉后"), ("t-left", "屉左")]:
        tray[k] = PanelSpec(k, k, v, row2[k])
    folds_t = [FoldSpec("t-front", "t-right", 90), FoldSpec("t-right", "t-back", 90),
               FoldSpec("t-back", "t-left", 90), FoldSpec("t-left", "glue2", 180)]

    max_y = max(p[1] for spec in sleeve.values() for p in spec.points)
    for spec in tray.values():
        spec.points = [(x, y + max_y + 40) for x, y in spec.points]
    dl = DielineData("drawer", "抽屉盒", dict(P), [DielinePiece("外套", sleeve, folds_s),
                                                  DielinePiece("内屉", tray, folds_t)])
    return _finalize(dl)


# 11) 套筒（0907）---------------------------------------------------------
def gen_sleeve(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    overlap = float(P.get("sleeveOverlap", W * 0.3))

    panels: Dict[str, PanelSpec] = {}
    row = _row_x([("glue", "glue", glue, W),
                  ("s-front", "sleeve", L, W),
                  ("s-right", "sleeve", H, W),
                  ("s-back", "sleeve", L, W),
                  ("s-left", "sleeve", H, W)])
    for k, v in [("glue", "糊头"), ("s-front", "套前"), ("s-right", "套右"),
                 ("s-back", "套后"), ("s-left", "套左")]:
        panels[k] = PanelSpec(k, k, v, row[k])
    folds = [FoldSpec("s-front", "s-right", 90), FoldSpec("s-right", "s-back", 90),
             FoldSpec("s-back", "s-left", 90), FoldSpec("s-left", "glue", 180)]
    piece = DielinePiece("主体", panels, folds)
    dl = DielineData("sleeve", "套筒", dict(P), [piece])
    return _finalize(dl)


# 12) 手提盒（带提手）-----------------------------------------------------
def gen_handle(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    hw = float(P.get("handleWidth", 60))
    hh = float(P.get("handleHeight", 20))

    dl = gen_tuck_end(P, with_dust=True)
    pc = dl.pieces[0]
    for pid in ("front", "back"):
        key = f"{pid}-tflap"
        if key in pc.panels:
            bx0, by0, bx1, by1 = _panel_bbox(pc.panels[key].points)
            cx = (bx0 + bx1) / 2
            cy = (by0 + by1) / 2
            pc.panels[key].holes.append(slot_points(cx - hw / 2, cy - hh / 2, hw, hh))
    dl.box_type = "handle"
    dl.label = "手提盒"
    return dl


# 13) 展示盒（斜面前壁 + 高后壁）-----------------------------------------
def gen_display(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    angle = float(P.get("displayAngle", 15))
    shelf = int(P.get("shelfCount", 1))

    panels: Dict[str, PanelSpec] = {}
    back_h = H * 1.2
    front_h = H * 0.7
    row = _row_x([("glue", "glue", glue, back_h),
                  ("back", "back", L, back_h),
                  ("right", "right", W, back_h),
                  ("front", "front", L, front_h),
                  ("left", "left", W, back_h)])
    fx0, fy0, fx1, fy1 = _panel_bbox(row["front"])
    cut = math.tan(math.radians(angle)) * front_h * 0.3
    front_poly = [(fx0, fy0), (fx1, fy0), (fx1 - cut, fy1), (fx0 + cut, fy1)]
    shelf_polys = []
    for i in range(shelf):
        y = -H * 0.35 * (i + 1)
        shelf_polys.append(rect_poly(fx0 + 5, y, L - 10, H * 0.15))
    for k, v in [("glue", "糊头"), ("back", "后壁"), ("right", "右壁"),
                 ("left", "左壁")]:
        panels[k] = PanelSpec(k, k, v, row[k])
    panels["front"] = PanelSpec("front", "front", "前壁（斜）", front_poly)
    for i, sp in enumerate(shelf_polys):
        panels[f"shelf-{i}"] = PanelSpec(f"shelf-{i}", "shelf", f"层板{i+1}", sp)
    top = _flap_top(panels["back"].points, W)
    panels["top"] = PanelSpec("top", "lid", "顶片", top)
    folds = [FoldSpec("back", "right", 90), FoldSpec("right", "front", 90),
             FoldSpec("front", "left", 90), FoldSpec("left", "glue", 180),
             FoldSpec("back", "top", 90)]
    piece = DielinePiece("主体", panels, folds)
    dl = DielineData("display", "展示盒", dict(P), [piece])
    return _finalize(dl)


# 14) 开窗盒 --------------------------------------------------------------
def gen_window(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    win_w = float(P.get("windowWidth", L * 0.6))
    win_h = float(P.get("windowHeight", H * 0.55))

    dl = gen_tuck_end(P, with_dust=True)
    pc = dl.pieces[0]
    front = pc.panels.get("front")
    if front:
        bx0, by0, bx1, by1 = _panel_bbox(front.points)
        cx = (bx0 + bx1) / 2
        cy = (by0 + by1) / 2
        front.holes.append(rect_poly(cx - win_w / 2, cy - win_h / 2, win_w, win_h))
        front.extra["film"] = P.get("filmType", "PET")
    dl.box_type = "window"
    dl.label = "开窗盒"
    return dl


# 15) 多件装（含隔板）-----------------------------------------------------
def gen_multi(P: dict) -> DielineData:
    L = float(P["length"]); W = float(P["width"]); H = float(P["height"])
    t = float(P.get("thickness", 0.45))
    glue = float(P.get("glueWidth", 15))
    cells = max(1, int(P.get("cellCount", 2)))
    div_t = float(P.get("dividerThickness", 2.0))

    dl = gen_tuck_end(P, with_dust=True)
    pc = dl.pieces[0]
    max_y = max(p[1] for spec in pc.panels.values() for p in spec.points)
    for i in range(cells - 1):
        x = 10 + i * (L / cells)
        div = rect_poly(x, max_y + 20, div_t, H)
        pc.panels[f"divider-{i}"] = PanelSpec(f"divider-{i}", "divider",
                                              f"隔板{i+1}", div)
    dl.box_type = "multi"
    dl.label = "多件装"
    return dl


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------
BOX_REGISTRY: Dict[str, dict] = {
    "tuck-end":     {"label": "单插盒", "gen": gen_tuck_end,
                     "params": ["length", "width", "height"],
                     "specials": [("tuckDepth", "插舌深度", 50)]},
    "double-tuck":  {"label": "双插盒", "gen": gen_double_tuck,
                     "params": ["length", "width", "height"],
                     "specials": [("tuckDepth", "插舌深度", 50), ("dustFlap", "防尘翼深度", 50)]},
    "hanging":      {"label": "吊孔盒", "gen": gen_hanging,
                     "params": ["length", "width", "height"],
                     "specials": [("holeDiameter", "吊孔直径", 25), ("hangTabHeight", "吊挂片高", 25)]},
    "auto-lock":    {"label": "扣底盒（自动锁底）", "gen": gen_auto_lock,
                     "params": ["length", "width", "height"],
                     "specials": [("tabDepth", "锁底翼深", 50), ("lockWidth", "锁扣宽", 35)]},
    "lock-bottom":  {"label": "锁底盒", "gen": gen_lock_bottom,
                     "params": ["length", "width", "height"],
                     "specials": [("lockDepth", "锁舌深", 30)]},
    "hinged-lid":   {"label": "翻盖盒（铰链盖）", "gen": gen_hinged_lid,
                     "params": ["length", "width", "height"],
                     "specials": [("lidHeight", "盖高", 40)]},
    "mailer":       {"label": "邮寄盒", "gen": gen_mailer,
                     "params": ["length", "width", "height"],
                     "specials": [("flapDepth", "盖片深", 50), ("tearStrip", "易撕条", 0)]},
    "airplane":     {"label": "飞机盒", "gen": gen_airplane,
                     "params": ["length", "width", "height"],
                     "specials": [("wingWidth", "翼宽", 50), ("tuckDepth", "插舌深", 35)]},
    "lid-base":     {"label": "天地盖", "gen": gen_lid_base,
                     "params": ["length", "width", "height"],
                     "specials": [("lidDepth", "盖深", 40), ("gapTolerance", "间隙", 0.5)]},
    "drawer":       {"label": "抽屉盒", "gen": gen_drawer,
                     "params": ["length", "width", "height"],
                     "specials": [("trayDepth", "屉深", 40), ("sleeveGap", "套间隙", 0.5)]},
    "sleeve":       {"label": "套筒", "gen": gen_sleeve,
                     "params": ["length", "width", "height"],
                     "specials": [("sleeveOverlap", "重叠量", 30)]},
    "handle":       {"label": "手提盒", "gen": gen_handle,
                     "params": ["length", "width", "height"],
                     "specials": [("handleWidth", "提手宽", 60), ("handleHeight", "提手高", 20)]},
    "display":      {"label": "展示盒", "gen": gen_display,
                     "params": ["length", "width", "height"],
                     "specials": [("displayAngle", "展示角度", 15), ("shelfCount", "层板数", 1)]},
    "window":       {"label": "开窗盒", "gen": gen_window,
                     "params": ["length", "width", "height"],
                     "specials": [("windowWidth", "窗宽", 60), ("windowHeight", "窗高", 55),
                                  ("filmType", "贴膜", "PET")]},
    "multi":        {"label": "多件装", "gen": gen_multi,
                     "params": ["length", "width", "height"],
                     "specials": [("cellCount", "格数", 2), ("dividerThickness", "隔板厚", 2.0)]},
}


def generate(box_type: str, parameters: dict) -> DielineData:
    """生成指定盒型刀模。"""
    if box_type not in BOX_REGISTRY:
        raise KeyError(f"未知盒型: {box_type}")
    entry = BOX_REGISTRY[box_type]
    return entry["gen"](parameters)


def list_box_types() -> List[dict]:
    return [{"id": k, "label": v["label"], "params": v["params"],
             "specials": v["specials"]} for k, v in BOX_REGISTRY.items()]
