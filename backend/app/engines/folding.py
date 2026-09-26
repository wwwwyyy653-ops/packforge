"""
Folding Engine — 3D 折叠引擎

基于铰链旋转的通用折纸模型：
- 每块面板在刀模平面内是一个多边形；
- 面板之间通过共享边（折痕）连接成折叠树；
- 根面板（面积最大）固定在世界平面，子面板绕铰链边旋转 fold_angle。

输出每个面板在给定折叠进度下的 3D 顶点，前端 Three.js 据此渲染并可动画。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .dieline import DielineData
from .geometry import shared_edge, polygon_area

Vec3 = Tuple[float, float, float]


@dataclass
class Basis:
    """三维仿射基底：O(原点), u/v/n(单位轴)。世界坐标 = O + u*x + v*y（z=0 平面）。"""
    O: Vec3
    u: Vec3
    v: Vec3
    n: Vec3

    def apply(self, p: Tuple[float, float]) -> Vec3:
        return (self.O[0] + self.u[0] * p[0] + self.v[0] * p[1],
                self.O[1] + self.u[1] * p[0] + self.v[1] * p[1],
                self.O[2] + self.u[2] * p[0] + self.v[2] * p[1])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(a: Vec3) -> float:
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


def _unit(a: Vec3) -> Vec3:
    n = _norm(a)
    if n < 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def child_basis(parent: Basis, hinge_a: Tuple[float, float],
                hinge_b: Tuple[float, float], theta_deg: float) -> Basis:
    """
    计算子面板的基底：子面板初始与父面板共面（共享铰链边 a-b），
    绕铰链旋转 theta 度（0=平铺，90=立起）。
    """
    a3 = parent.apply(hinge_a)
    b3 = parent.apply(hinge_b)
    u = _unit(_sub(b3, a3))
    n_plane = parent.n
    v_candidate = _cross(n_plane, u)
    v = v_candidate
    cos_t, sin_t = math.cos(math.radians(theta_deg)), math.sin(math.radians(theta_deg))
    u_c = u
    v_c = (v[0] * cos_t + n_plane[0] * sin_t,
           v[1] * cos_t + n_plane[1] * sin_t,
           v[2] * cos_t + n_plane[2] * sin_t)
    n_c = (n_plane[0] * cos_t - v[0] * sin_t,
           n_plane[1] * cos_t - v[1] * sin_t,
           n_plane[2] * cos_t - v[2] * sin_t)
    O = (a3[0] - u_c[0] * hinge_a[0] - v_c[0] * hinge_a[1],
         a3[1] - u_c[1] * hinge_a[0] - v_c[1] * hinge_a[1],
         a3[2] - u_c[2] * hinge_a[0] - v_c[2] * hinge_a[1])
    return Basis(O, u_c, v_c, n_c)


def build_folding_3d(dl: DielineData, progress: float = 1.0,
                     max_angle: float = 180.0) -> Dict[str, dict]:
    """
    构建折叠树并计算每块面板的 3D 顶点。

    返回: {panel_key: {id, role, name, points3d: [[x,y,z],...], holes3d: [...]}}
    progress: 0(平铺) ~ 1(完全折叠)
    """
    panels = dl.all_panels
    folds = dl.all_folds
    root_key = max(panels, key=lambda k: abs(polygon_area(panels[k].points)))

    adj: Dict[str, List[Tuple[str, float, Tuple, Tuple]]] = {k: [] for k in panels}
    for f in folds:
        if f.a not in panels or f.b not in panels:
            continue
        e = shared_edge(panels[f.a].points, panels[f.b].points)
        if e is None:
            continue
        hinge_a, hinge_b = e
        pa_c = _panel_center(panels[f.a].points)
        pb_c = _panel_center(panels[f.b].points)
        u = _unit((hinge_b[0] - hinge_a[0], hinge_b[1] - hinge_a[1], 0.0))
        v_cand = (-u[1], u[0], 0.0)
        s_b = (pb_c[0] - hinge_a[0]) * v_cand[0] + (pb_c[1] - hinge_a[1]) * v_cand[1]
        if s_b < 0:
            v_cand = (-v_cand[0], -v_cand[1], 0.0)
        adj[f.a].append((f.b, f.angle, hinge_a, hinge_b))
        adj[f.b].append((f.a, f.angle, hinge_a, hinge_b))

    basis: Dict[str, Basis] = {}
    parent_of: Dict[str, str] = {}
    hinge_of: Dict[str, Tuple[Tuple, Tuple]] = {}
    angle_of: Dict[str, float] = {}

    root_poly = panels[root_key].points
    bx0 = min(p[0] for p in root_poly)
    by0 = min(p[1] for p in root_poly)
    basis[root_key] = Basis((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    parent_of[root_key] = ""
    order = [root_key]
    visited = {root_key}
    while order:
        cur = order.pop(0)
        for (nxt, ang, ha, hb) in adj[cur]:
            if nxt in visited:
                continue
            visited.add(nxt)
            parent_of[nxt] = cur
            hinge_of[nxt] = (ha, hb)
            angle_of[nxt] = ang
            theta = ang * progress if progress is not None else ang
            basis[nxt] = child_basis(basis[cur], ha, hb, theta)
            order.append(nxt)

    out: Dict[str, dict] = {}
    for key, spec in panels.items():
        if key not in basis:
            b = Basis((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
            basis[key] = b
        pts3 = [basis[key].apply(p) for p in spec.points]
        holes3 = [[basis[key].apply(h) for h in hole] for hole in spec.holes]
        out[key] = {
            "id": key,
            "role": spec.role,
            "name": spec.name,
            "parent": parent_of.get(key, ""),
            "foldAngle": angle_of.get(key, 0),
            "points3d": pts3,
            "holes3d": holes3,
        }
    return out


def _panel_center(poly) -> Tuple[float, float]:
    n = len(poly)
    if n == 0:
        return (0, 0)
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


def folding_tree(dl: DielineData) -> List[dict]:
    """输出折叠树（供前端动画逐面板播放）。"""
    panels = dl.all_panels
    folds = dl.all_folds
    root_key = max(panels, key=lambda k: abs(polygon_area(panels[k].points)))
    adj = {k: [] for k in panels}
    for f in folds:
        if f.a not in panels or f.b not in panels:
            continue
        e = shared_edge(panels[f.a].points, panels[f.b].points)
        if e is None:
            continue
        adj[f.a].append((f.b, f.angle, e[0], e[1]))
        adj[f.b].append((f.a, f.angle, e[0], e[1]))
    tree: List[dict] = []
    visited = {root_key}
    order = [root_key]
    while order:
        cur = order.pop(0)
        children = []
        for (nxt, ang, ha, hb) in adj[cur]:
            if nxt not in visited:
                visited.add(nxt)
                children.append(nxt)
                order.append(nxt)
        tree.append({"id": cur, "name": panels[cur].name, "role": panels[cur].role,
                     "children": children})
    return tree
