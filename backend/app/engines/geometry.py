"""
Geometry Engine — 基础几何服务

提供 2D 平面几何核心：点、线段、多边形、面积/包围盒/自相交检测/共享边检测。
所有坐标单位为 mm，浮点精度 1e-6。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Polygon = List[Point]


# ---------------------------------------------------------------------------
# 基础类型
# ---------------------------------------------------------------------------
@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def contains(self, p: Point, eps: float = 1e-6) -> bool:
        return (self.x - eps <= p[0] <= self.right + eps
                and self.y - eps <= p[1] <= self.bottom + eps)


@dataclass
class PathData:
    """通用路径：顶点序列 + 是否闭合"""
    points: List[Point] = field(default_factory=list)
    closed: bool = True

    def bbox(self) -> Rect:
        if not self.points:
            return Rect(0, 0, 0, 0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def area(self) -> float:
        return polygon_area(self.points)

    def length(self) -> float:
        n = len(self.points)
        if n < 2:
            return 0.0
        total = 0.0
        for i in range(n):
            a, b = self.points[i], self.points[(i + 1) % n]
            total += math.hypot(b[0] - a[0], b[1] - a[1])
        return total


# ---------------------------------------------------------------------------
# 基础计算
# ---------------------------------------------------------------------------
def dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def polygon_area(poly: Polygon) -> float:
    """鞋带公式（有符号面积），逆时针为正。"""
    n = len(poly)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def polygon_centroid(poly: Polygon) -> Point:
    """多边形重心（对任意简单多边形有效）。"""
    n = len(poly)
    if n < 3:
        return (poly[0][0], poly[0][1]) if poly else (0, 0)
    area = polygon_area(poly)
    if abs(area) < 1e-9:
        return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)
    cx = cy = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        f = x1 * y2 - x2 * y1
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    return (cx / (6 * area), cy / (6 * area))


def polygon_bbox(poly: Polygon) -> Rect:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def on_segment(p: Point, a: Point, b: Point, eps: float = 1e-9) -> bool:
    """点是否在线段 ab 上（含端点）。"""
    if abs(cross(a, b, p)) > eps:
        return False
    return (min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
            and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps)


def segments_intersect(a: Point, b: Point, c: Point, d: Point,
                       eps: float = 1e-9) -> bool:
    """判断两线段是否相交（含端点接触）。"""
    d1 = cross(c, d, a)
    d2 = cross(c, d, b)
    d3 = cross(a, b, c)
    d4 = cross(a, b, d)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
       ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True
    if abs(d1) <= eps and on_segment(a, c, d, eps):
        return True
    if abs(d2) <= eps and on_segment(b, c, d, eps):
        return True
    if abs(d3) <= eps and on_segment(c, a, b, eps):
        return True
    if abs(d4) <= eps and on_segment(d, a, b, eps):
        return True
    return False


def has_self_intersection(poly: Polygon, eps: float = 1e-9) -> bool:
    """自相交检测（Bentley-Ottmann 的朴素实现，用于 <500 顶点）。"""
    n = len(poly)
    if n < 4:
        return False
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 1, n):
            c, d = poly[j], poly[(j + 1) % n]
            if i == j:
                continue
            # 跳过相邻边（共享端点）
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if segments_intersect(a, b, c, d, eps):
                # 排除仅共享端点
                shared = {a, b} & {c, d}
                if shared:
                    continue
                return True
    return False


def is_convex(poly: Polygon) -> bool:
    n = len(poly)
    if n < 4:
        return True
    signs = []
    for i in range(n):
        o = poly[i]
        a = poly[(i + 1) % n]
        b = poly[(i + 2) % n]
        z = cross(o, a, b)
        if abs(z) > 1e-9:
            signs.append(1 if z > 0 else -1)
    return len(set(signs)) <= 1


def edges_of(poly: Polygon) -> List[Tuple[Point, Point]]:
    n = len(poly)
    return [(poly[i], poly[(i + 1) % n]) for i in range(n)]


def edge_key(a: Point, b: Point, eps: float = 1e-3) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """边哈希键（按长度+方向量化），用于共享边匹配。"""
    ax, ay = round(a[0] / eps), round(a[1] / eps)
    bx, by = round(b[0] / eps), round(b[1] / eps)
    return ((ax, ay), (bx, by)) if (ax, ay) <= (bx, by) else ((bx, by), (ax, ay))


def shared_edge(poly_a: Polygon, poly_b: Polygon,
                eps: float = 1e-3) -> Optional[Tuple[Point, Point]]:
    """返回两多边形共享的边（如存在）。"""
    set_a = set()
    for e in edges_of(poly_a):
        set_a.add(edge_key(e[0], e[1], eps))
    for e in edges_of(poly_b):
        if edge_key(e[0], e[1], eps) in set_a:
            return (e[0], e[1])
    return None


def simplify_axis(poly: Polygon) -> Polygon:
    """轴向去冗余：移除共线中间点（用于生成干净的刀模 SVG/DXF）。"""
    if len(poly) < 3:
        return list(poly)
    out = []
    n = len(poly)
    for i in range(n):
        prev = poly[(i - 1) % n]
        cur = poly[i]
        nxt = poly[(i + 1) % n]
        if abs(cross(prev, cur, nxt)) < 1e-6:
            continue
        out.append(cur)
    if len(out) < 3:
        return list(poly)
    return out


def translate(poly: Polygon, dx: float, dy: float) -> Polygon:
    return [(x + dx, y + dy) for x, y in poly]


def scale(poly: Polygon, sx: float, sy: float) -> Polygon:
    return [(x * sx, y * sy) for x, y in poly]


def rotate_point(p: Point, center: Point, angle_deg: float) -> Point:
    """绕中心旋转（角度制）。"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    x, y = p[0] - center[0], p[1] - center[1]
    return (center[0] + x * c - y * s, center[1] + x * s + y * c)


def rotate(poly: Polygon, center: Point, angle_deg: float) -> Polygon:
    return [rotate_point(p, center, angle_deg) for p in poly]


def rect_poly(x: float, y: float, w: float, h: float) -> Polygon:
    """顺时针矩形（刀模习惯：外轮廓顺时针）。"""
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def circle_points(cx: float, cy: float, r: float, n: int = 48) -> Polygon:
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def slot_points(x: float, y: float, length: float, width: float) -> Polygon:
    """水平狭槽矩形（顺时针）。"""
    return [(x, y), (x + length, y), (x + length, y + width), (x, y + width)]
