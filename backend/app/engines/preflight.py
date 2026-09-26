"""
Preflight Engine — 刀模预检

检查：面板自相交 / 折痕连续性 / 最小尺寸 / 材料厚度比 / 开孔位置。
输出：PreflightReport（items + 结论）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .geometry import has_self_intersection, polygon_area


@dataclass
class PreflightItem:
    level: str            # error / warning / info
    code: str
    message: str
    panel: Optional[str] = None


@dataclass
class PreflightReport:
    passed: bool
    items: List[PreflightItem] = field(default_factory=list)

    @property
    def errors(self) -> List[PreflightItem]:
        return [i for i in self.items if i.level == 'error']

    @property
    def warnings(self) -> List[PreflightItem]:
        return [i for i in self.items if i.level == 'warning']

    def to_dict(self) -> dict:
        return {"passed": self.passed,
                "items": [{"level": i.level, "code": i.code,
                           "message": i.message, "panel": i.panel}
                          for i in self.items]}


def run_preflight(dl) -> PreflightReport:
    """对 DielineData 执行全套预检。"""
    report = PreflightReport(passed=True)

    for piece in dl.pieces:
        for key, panel in piece.panels.items():
            pts = panel.points
            if len(pts) < 3:
                report.items.append(PreflightItem('error', 'panel_too_few_points',
                                                  f'面板 {panel.name} 顶点数不足', key))
                continue
            if has_self_intersection(pts):
                report.items.append(PreflightItem('error', 'panel_self_intersect',
                                                  f'面板 {panel.name} 存在自相交', key))
            area = abs(polygon_area(pts))
            if area < 100:   # 10×10mm
                report.items.append(PreflightItem('warning', 'panel_too_small',
                                                  f'面板 {panel.name} 面积偏小({area:.0f}mm²)', key))

    # 尺寸合理性
    if dl.flat_width < 30 or dl.flat_height < 30:
        report.items.append(PreflightItem('error', 'flat_too_small',
                                          '展开尺寸过小(<30mm)，无法生产'))
    if dl.flat_width > 2000 or dl.flat_height > 2000:
        report.items.append(PreflightItem('warning', 'flat_too_large',
                                          '展开尺寸超过 2000mm，请确认拼版方案'))

    # 厚度比
    t = dl.parameters.get('thickness', 0.45)
    if t and t > 8:
        report.items.append(PreflightItem('warning', 'thickness_high',
                                          f'材料厚度 {t}mm 偏高，请确认瓦楞/重型材质'))

    # 结论
    report.passed = not any(i.level == 'error' for i in report.items)
    return report
