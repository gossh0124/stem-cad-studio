"""lib/verification/l2_layout.py — VS-L2 schematic 排版品質（遮擋 / 交叉）。

L2 視覺品質層（non-blocking，問題回 WARN）。偵測使用者反映的：
  no_label_overlap   wire/pin 文字標籤互相重疊（走線標註被字體遮擋）
  wire_crossings_ok  接線交叉數過多（排版雜亂）

純函數 audit_schematic_layout 可單測；check_schematic_svg 解析 SVG 後呼叫。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .report import CheckResult, VerificationReport, Verdict

_SVG_NS = "{http://www.w3.org/2000/svg}"
_CHAR_W_RATIO = 0.6  # 估算文字寬度：字數 × font_size × ratio


def _bbox_overlap(a: tuple, b: tuple) -> bool:
    """a, b = (x, y, w, h)。回傳是否重疊（重疊面積 > 0）。"""
    ox = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    oy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return ox > 0 and oy > 0


def _seg_intersect(p1, p2, p3, p4) -> bool:
    """線段 p1p2 與 p3p4 是否相交（端點共用不算）。"""
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
    # 共用端點 → 視為不交叉（同 pin 出發）
    if p1 in (p3, p4) or p2 in (p3, p4):
        return False
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def audit_schematic_layout(labels: list, wires: list, *, name: str | None = None,
                           max_crossings: int | None = None) -> VerificationReport:
    """labels: [{text, x, y, w, h}]；wires: [(x1, y1, x2, y2)]。"""
    rpt = VerificationReport(artifact=name or "<schematic>", artifact_type="schematic_layout")

    # ── label ↔ label 重疊（文字互相遮擋）──
    overlaps = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            if _bbox_overlap((a["x"], a["y"], a["w"], a["h"]),
                             (b["x"], b["y"], b["w"], b["h"])):
                overlaps.append(f"{a.get('text', '?')}↔{b.get('text', '?')}")
    if overlaps:
        rpt.add(CheckResult("L2", "no_label_overlap", Verdict.WARN,
                            message="文字標籤互相重疊（走線標註被遮擋）",
                            metric={"n": len(overlaps), "pairs": overlaps[:8]}))
    else:
        rpt.add(CheckResult("L2", "no_label_overlap", Verdict.PASS,
                            metric={"n_labels": len(labels)}))

    # ── wire ↔ wire 交叉 ──
    crossings = 0
    for i in range(len(wires)):
        for j in range(i + 1, len(wires)):
            w1, w2 = wires[i], wires[j]
            if _seg_intersect((w1[0], w1[1]), (w1[2], w1[3]),
                              (w2[0], w2[1]), (w2[2], w2[3])):
                crossings += 1
    thresh = max_crossings if max_crossings is not None else max(2, len(wires) // 2)
    if crossings > thresh:
        rpt.add(CheckResult("L2", "wire_crossings_ok", Verdict.WARN,
                            message=f"接線交叉過多（{crossings} > {thresh}）排版雜亂",
                            metric={"crossings": crossings, "threshold": thresh}))
    else:
        rpt.add(CheckResult("L2", "wire_crossings_ok", Verdict.PASS,
                            metric={"crossings": crossings}))
    return rpt


def _parse_labels_and_wires(svg: str):
    """從 SVG 抽 text 標籤（估 bbox）+ wire path 端點。"""
    root = ET.fromstring(svg)
    labels = []
    for t in root.iter(f"{_SVG_NS}text"):
        txt = (t.text or "").strip()
        if not txt:
            continue
        try:
            x = float(t.attrib.get("x", 0))
            y = float(t.attrib.get("y", 0))
            fs = float(t.attrib.get("font-size", 10))
        except ValueError:
            continue
        w = len(txt) * fs * _CHAR_W_RATIO
        anchor = t.attrib.get("text-anchor", "start")
        if anchor == "middle":
            x -= w / 2
        labels.append({"text": txt, "x": x, "y": y - fs, "w": w, "h": fs})

    wires = []
    # wire = path with stroke-dasharray (信號線)；端點取 M 起點與最後座標。
    # 只認真正帶 stroke-dasharray（屬性或 inline style）或 wire class 的 path，
    # 避免邊框/元件外框等裝飾性 path 被誤計為信號線而灌水交叉數與門檻。
    for p in root.iter(f"{_SVG_NS}path"):
        style = p.attrib.get("style", "")
        cls = p.attrib.get("class", "")
        is_wire = (
            p.attrib.get("stroke-dasharray") is not None
            or "stroke-dasharray" in style
            or "wire" in cls.split()
        )
        if not is_wire:
            continue
        d = p.attrib.get("d", "")
        nums = re.findall(r"-?\d+\.?\d*", d)
        if len(nums) >= 4:
            x1, y1 = float(nums[0]), float(nums[1])
            x2, y2 = float(nums[-2]), float(nums[-1])
            wires.append((x1, y1, x2, y2))
    return labels, wires


def check_schematic_svg(svg: str, *, name: str | None = None,
                        max_crossings: int | None = None) -> VerificationReport:
    """解析 schematic SVG → 偵測 label 遮擋 + wire 交叉。"""
    try:
        labels, wires = _parse_labels_and_wires(svg)
    except ET.ParseError as exc:
        rpt = VerificationReport(artifact=name or "<schematic>", artifact_type="schematic_layout")
        rpt.add(CheckResult("L0", "parseable", Verdict.FAIL, message=f"SVG 解析失敗: {exc}"))
        return rpt
    return audit_schematic_layout(labels, wires, name=name, max_crossings=max_crossings)
