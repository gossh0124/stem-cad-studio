"""lib/verification/report.py — Verification Spine 統一報告框架。

所有產出物驗證（schematic / 3D / assembly）共用此報告結構。

核心原則：正確性判定必須**可計算、可量化、有 verdict gate**，
不依賴肉眼看截圖。任何宣告「成功」前都必須通過此報告的 gate。

Layer 定義：
  L0  產出完整性（檔案存在、非空白、可解析）           ← blocking
  L1  結構/語義正確（netlist 連通、watertight、spec 符合）← blocking
  L2  排版/視覺品質（遮擋、交叉、視角齊全）              ← non-blocking（先警告）
  L3  黃金回歸（對照已確認基準）                         ← non-blocking（先警告）

verdict 聚合規則：
  - 任何 blocking 層（L0/L1）出現 FAIL → 整體 FAIL
  - 非 blocking 層（L2/L3）的 FAIL 自動降級為警告，不擋 gate（除非 strict）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


BLOCKING_LAYERS = frozenset({"L0", "L1"})
_MARK = {Verdict.PASS: "✅", Verdict.FAIL: "❌", Verdict.WARN: "⚠️"}


@dataclass
class CheckResult:
    """單一檢查項的結果。

    layer:     "L0".."L3"
    name:      檢查項名稱
    verdict:   PASS / FAIL / WARN
    metric:    量化值（dict，例如 {"variance": 1234.5, "n_faces": 5152}）
    threshold: 門檻說明（可選）
    message:   人類可讀說明
    evidence:  佐證（路徑、細節 dict 等，可選）
    """
    layer: str
    name: str
    verdict: Verdict
    metric: dict = field(default_factory=dict)
    threshold: str | None = None
    message: str = ""
    evidence: dict | None = None

    @property
    def is_blocking_fail(self) -> bool:
        return self.verdict == Verdict.FAIL and self.layer in BLOCKING_LAYERS


@dataclass
class VerificationReport:
    """單一產出物的完整驗證報告。"""
    artifact: str
    artifact_type: str  # svg / png / mesh / assembly / netlist ...
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, check: CheckResult) -> CheckResult:
        self.checks.append(check)
        return check

    def extend(self, checks: list[CheckResult]) -> None:
        self.checks.extend(checks)

    # ── 聚合 ────────────────────────────────────────────────
    @property
    def verdict(self) -> Verdict:
        """整體判定：任何 blocking 層 FAIL → FAIL，否則 PASS。"""
        if any(c.is_blocking_fail for c in self.checks):
            return Verdict.FAIL
        return Verdict.PASS

    @property
    def has_nonblocking_fail(self) -> bool:
        return any(c.verdict == Verdict.FAIL and c.layer not in BLOCKING_LAYERS
                   for c in self.checks)

    def counts(self) -> dict:
        out = {"PASS": 0, "FAIL": 0, "WARN": 0}
        for c in self.checks:
            out[c.verdict.value] += 1
        return out

    def exit_code(self, *, strict: bool = False) -> int:
        """0 = 通過。strict 時非 blocking FAIL 也擋。"""
        if self.verdict == Verdict.FAIL:
            return 1
        if strict and self.has_nonblocking_fail:
            return 1
        return 0

    # ── 輸出 ────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "artifact": self.artifact,
            "artifact_type": self.artifact_type,
            "verdict": self.verdict.value,
            "counts": self.counts(),
            "checks": [asdict(c) for c in self.checks],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent,
                          default=str)

    def render_text(self) -> str:
        lines = []
        v = self.verdict
        lines.append(f"{_MARK[v]} [{v.value}] {self.artifact} ({self.artifact_type})")
        for c in self.checks:
            mark = _MARK[c.verdict]
            line = f"  {mark} {c.layer} {c.name}"
            if c.message:
                line += f" — {c.message}"
            lines.append(line)
            if c.metric:
                metric_str = ", ".join(f"{k}={v}" for k, v in c.metric.items())
                lines.append(f"        {metric_str}")
        c = self.counts()
        lines.append(f"  ── {c['PASS']} pass / {c['FAIL']} fail / {c['WARN']} warn")
        return "\n".join(lines)


def gate(report: VerificationReport, *, strict: bool = False) -> int:
    """印出報告並回傳 exit code（供腳本 sys.exit 使用）。

    使用範例：
        import sys
        sys.exit(gate(report))
    """
    print(report.render_text())
    code = report.exit_code(strict=strict)
    if code != 0:
        print(f"\n[FAIL] exit {code} -- verification did not pass.")
    return code
