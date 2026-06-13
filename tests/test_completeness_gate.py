"""PB1 (Path B / D5): SSOT completeness gate.

Every component class in verified.json must have the SSOT fields its render paths
(wiring / schematic / 3d) need to be DERIVED, or be explicitly WIP-whitelisted with a
reason. This enforces feedback_template_best_free_input_no_fallback: free input never
silently falls back — an incomplete component yields a named gap, not a generic box.
"""
from typing import Any

import pytest

from lib.ssot_completeness import audit_all, check_completeness, WIP_WHITELIST


class TestCompletenessGate:
    def test_no_incomplete_classes(self):
        """Every verified.json class is render-complete OR explicitly WIP-whitelisted."""
        res = audit_all()
        assert not res["incomplete"], (
            "SSOT-incomplete classes (fill verified.json, or add to WIP_WHITELIST with a reason):\n"
            + "\n".join(
                f"  {c}: " + "; ".join(f"[{g.path}] {g.field}" for g in gaps)
                for c, gaps in res["incomplete"].items()))

    def test_wip_whitelist_is_justified(self):
        """No dead WIP entries: a whitelisted class must actually be incomplete on the
        whitelisted path (else remove the entry — the SSOT is already complete)."""
        for cls, paths in WIP_WHITELIST.items():
            r = check_completeness(cls, tuple(paths.keys()))
            assert r.is_wip or not r.complete, (
                f"{cls} whitelisted for {list(paths)} but is actually complete — remove dead WIP entry")

    def test_signal_components_complete(self):
        for cls in ("Sensor-PIR-class", "Sensor-TempHumid-class",
                    "Relay-Module-class", "Display-OLED-class", "Motor-Servo-class"):
            assert check_completeness(cls).complete, f"{cls} should be render-complete"

    def test_power_source_complete_via_pwr_pin(self):
        for cls in ("Battery-AA-class", "USB-5V-class", "AC-Adapter-class"):
            assert check_completeness(cls).complete, f"{cls} power source should be complete (PWR pin)"

    def test_missing_class_is_explicit_not_silent(self):
        """A missing-SSOT class yields named gaps with reasons, never a silent empty pass."""
        r = check_completeness("No-Such-Class")
        assert not r.ok and r.gaps and all(g.reason for g in r.gaps)


class TestCompletenessRuntimeGate:
    """PB1 runtime: api_wiring/api_schematic refuse incomplete components with a named
    SSOT_INCOMPLETE (422) instead of silently rendering a wrong circuit."""

    def test_check_components_passes_valid_set(self):
        from lib.ssot_completeness import check_components
        assert check_components(["Sensor-PIR-class", "Relay-Module-class", "TempHumid"]) == []

    def test_resolve_class_variants(self):
        from lib.ssot_completeness import _resolve_class, _load
        ssot = _load()
        assert _resolve_class("Sensor-PIR-class", ssot) == "Sensor-PIR-class"  # exact
        assert _resolve_class("Sensor-PIR", ssot) == "Sensor-PIR-class"        # minus -class
        assert _resolve_class("Totally-Unknown-XYZ", ssot) is None            # unknown → None

    def test_wip_power_component_not_blocked_in_outputs(self):
        # WIP classes are ok=True (blocked-but-flagged on frontend, not a hard API error)
        from lib.ssot_completeness import check_components
        assert check_components(["USB-Adapter-class"]) == []

    def test_incomplete_detail_shape(self):
        from lib.ssot_completeness import check_completeness, incomplete_detail
        r = check_completeness("No-Such-Class")
        d = incomplete_detail([("No-Such-Class", r)])
        assert d["error"] == "SSOT_INCOMPLETE"
        assert d["components"][0]["component"] == "No-Such-Class"
        assert all("reason" in m for m in d["components"][0]["missing"])

    # ── api_schematic gate 接上(兌現本類 docstring 對 api_schematic 的承諾)──────
    # 先前僅 api_wiring 接 completeness gate;api_schematic 只攔 PinAllocationError,
    # 不完整元件會靜默畫出 fallback 原理圖。此處鎖死 api_schematic 亦 refuse(422)。

    def test_api_schematic_refuses_incomplete(self, monkeypatch):
        """api_schematic 對不完整元件回 422(非靜默渲染)。全 43 SSOT class 現皆 complete/WIP,
        無法用真元件觸發 → patch 偵測函式本身,證 route 確有接上 gate 並轉 422。"""
        pytest.importorskip("build123d")  # API route boots full pipeline (lib.cad/build123d)
        monkeypatch.setenv("CADHLLM_ALLOW_DEV_SECRET", "1")
        import asyncio
        from fastapi import HTTPException
        import lib.ssot_completeness as ssc
        from services.gateway.routes_design import api_schematic, DesignRequest
        r = ssc.check_completeness("No-Such-Class")  # 真實「無 SSOT entry」的 gaps
        monkeypatch.setattr(ssc, "check_components",
                            lambda names, paths=("wiring",): [("No-Such-Class", r)])
        req = DesignRequest(brain="Arduino", outputs=["No-Such-Class"], sensors=[], power="USB-5V")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(api_schematic(req))
        assert ei.value.status_code == 422
        detail: Any = ei.value.detail  # HTTPException.detail stub 型別為 str;實際為 dict
        assert isinstance(detail, dict) and detail["error"] == "SSOT_INCOMPLETE"

    def test_api_schematic_renders_complete_set(self, monkeypatch):
        """happy path:完整元件集 → api_schematic 正常回 raw_svg(gate 不誤擋)。"""
        pytest.importorskip("build123d")  # API route boots full pipeline (lib.cad/build123d)
        monkeypatch.setenv("CADHLLM_ALLOW_DEV_SECRET", "1")
        import asyncio
        from services.gateway.routes_design import api_schematic, DesignRequest
        req = DesignRequest(brain="Arduino", outputs=["Relay-Module-class"],
                            sensors=["Sensor-PIR-class"], power="USB-5V")
        out = asyncio.run(api_schematic(req))
        assert isinstance(out, dict) and out.get("raw_svg")
