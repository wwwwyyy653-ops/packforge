"""
Export Engine — 导出服务

支持 SVG / DXF / PDF 三种格式输出刀模图。
- SVG: 矢量，可直接浏览器查看/编辑
- DXF: R12 文本格式，可直接下发激光刀模机
- PDF: 用于打印与规格书
"""
from __future__ import annotations

import io
import math
from typing import List, Tuple

from .dieline import DielineData
from .geometry import polygon_centroid


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------
def _polyline_svg(pts: List[Tuple[float, float]], closed: bool = True) -> str:
    d = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    if closed:
        d += " Z"
    return d


def export_svg(dl: DielineData, scale: float = 1.0, show_labels: bool = True) -> str:
    w = dl.flat_width + 40
    h = dl.flat_height + 40
    sw = "1.0"
    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}mm" '
                 f'height="{h:.1f}mm" viewBox="0 0 {w:.1f} {h:.1f}">')
    parts.append('<rect x="0" y="0" width="%.1f" height="%.1f" fill="white"/>' % (w, h))
    parts.append(f'<g transform="translate(20,20) scale({scale})">')

    panels = dl.all_panels
    for key, spec in panels.items():
        parts.append(f'<path d="{_polyline_svg(spec.points)}" fill="#f2f2f2" '
                     f'stroke="none"/>')
    for key, spec in panels.items():
        parts.append(f'<path d="{_polyline_svg(spec.points)}" fill="none" '
                     f'stroke="#e11d48" stroke-width="{sw}"/>')
        for hole in spec.holes:
            parts.append(f'<path d="{_polyline_svg(hole)}" fill="white" '
                         f'stroke="#e11d48" stroke-width="{sw}"/>')
    seen = set()
    for f in dl.all_folds:
        pa = panels.get(f.a)
        pb = panels.get(f.b)
        if not pa or not pb:
            continue
        e = _shared_edge_pts(pa.points, pb.points)
        if e is None:
            continue
        key = tuple(sorted((round(e[0][0], 1), round(e[0][1], 1),
                            round(e[1][0], 1), round(e[1][1], 1))))
        if key in seen:
            continue
        seen.add(key)
        parts.append(f'<line x1="{e[0][0]:.2f}" y1="{e[0][1]:.2f}" '
                     f'x2="{e[1][0]:.2f}" y2="{e[1][1]:.2f}" '
                     f'stroke="#2563eb" stroke-width="{sw}" stroke-dasharray="4,2"/>')
    if show_labels:
        for key, spec in panels.items():
            cx, cy = polygon_centroid(spec.points)
            parts.append(f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="5" '
                         f'text-anchor="middle" fill="#334155">{spec.name}</text>')
    parts.append('</g></svg>')
    return "\n".join(parts)


def _shared_edge_pts(poly_a, poly_b):
    from .geometry import edges_of, edge_key
    set_a = set()
    for e in edges_of(poly_a):
        set_a.add(edge_key(e[0], e[1]))
    for e in edges_of(poly_b):
        if edge_key(e[0], e[1]) in set_a:
            return (e[0], e[1])
    return None


# ---------------------------------------------------------------------------
# DXF (R12)
# ---------------------------------------------------------------------------
def export_dxf(dl: DielineData) -> str:
    lines: List[str] = []
    lines.append("0\nSECTION\n2\nHEADER\n0\nENDSEC")
    lines.append("0\nSECTION\n2\nTABLES\n0\nENDSEC")
    lines.append("0\nSECTION\n2\nENTITIES")
    panels = dl.all_panels
    lines.append("0\nLAYER\n2\nCUT\n70\n0\n62\n1\n6\nCONTINUOUS\n0\nLAYER\n2\nCREASE\n70\n0\n62\n5\n6\nDASHED\n0\nLAYER\n2\nHOLE\n70\n0\n62\n7\n6\nCONTINUOUS")
    for key, spec in panels.items():
        _dxf_polyline(lines, spec.points, "CUT")
        for hole in spec.holes:
            _dxf_polyline(lines, hole, "HOLE")
    seen = set()
    for f in dl.all_folds:
        pa = panels.get(f.a)
        pb = panels.get(f.b)
        if not pa or not pb:
            continue
        e = _shared_edge_pts(pa.points, pb.points)
        if e is None:
            continue
        key = tuple(sorted((round(e[0][0], 1), round(e[0][1], 1),
                            round(e[1][0], 1), round(e[1][1], 1))))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"0\nLINE\n8\nCREASE\n10\n{e[0][0]:.3f}\n20\n{e[0][1]:.3f}\n30\n0.0\n"
                     f"11\n{e[1][0]:.3f}\n21\n{e[1][1]:.3f}\n31\n0.0")
    lines.append("0\nENDSEC\n0\nEOF")
    return "\n".join(lines)


def _dxf_polyline(lines: List[str], pts, layer: str):
    lines.append(f"0\nPOLYLINE\n8\n{layer}\n66\n1\n70\n1")
    for x, y in pts:
        lines.append(f"0\nVERTEX\n8\n{layer}\n10\n{x:.3f}\n20\n{y:.3f}\n30\n0.0")
    lines.append("0\nSEQEND")


# ---------------------------------------------------------------------------
# PDF（用极简 xref 手写构造，不依赖第三方库）
# ---------------------------------------------------------------------------
def export_pdf(dl: DielineData) -> bytes:
    """生成单页 PDF：刀模图（切割线黑色、折痕线灰色虚线）。"""
    w, h = dl.flat_width + 60, dl.flat_height + 60
    objs: List[str] = []
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.1f %.1f] "
                "/Contents 4 0 R >>" % (w, h))
    stream_lines: List[str] = []
    stream_lines.append("0.2 w 0 0 0 RG")
    scale = 1.0
    ox, oy = 30.0, 30.0
    panels = dl.all_panels
    for key, spec in panels.items():
        _pdf_path(stream_lines, spec.points, ox, oy, scale, True, "S", h)
        for hole in spec.holes:
            _pdf_path(stream_lines, hole, ox, oy, scale, True, "S", h)
    stream_lines.append("0.6 w 0.4 0.4 0.4 RG [2 1.5] 0 d")
    for f in dl.all_folds:
        pa = panels.get(f.a)
        pb = panels.get(f.b)
        if not pa or not pb:
            continue
        e = _shared_edge_pts(pa.points, pb.points)
        if e is None:
            continue
        x1, y1 = e[0][0] + ox, h - (e[0][1] + oy)
        x2, y2 = e[1][0] + ox, h - (e[1][1] + oy)
        stream_lines.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")
    content = "\n".join(stream_lines)
    objs.append("<< /Length %d >>\nstream\n%s\nendstream" % (len(content.encode()), content))

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, o in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1"))
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objs)+1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode())
    return out.getvalue()


def _pdf_path(lines: List[str], pts, ox, oy, scale, closed=True, op="S", page_h=500.0):
    if not pts:
        return
    for i, (x, y) in enumerate(pts):
        px = x * scale + ox
        py = page_h - (y + oy)
        lines.append(f"{px:.2f} {py:.2f} m" if i == 0 else f"{px:.2f} {py:.2f} l")
    if closed:
        lines.append("h")
    lines.append(op)
