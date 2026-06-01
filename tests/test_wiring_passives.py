"""Phase 2 step 1：被動元件標註（refdes/location/purchasable）測試。

驗證 annotate_passives 與 to_json 接入:RefDes 確定性、location 拓撲判定、
purchasable 分流，以及「不污染共享模板/常數」（跨呼叫一致）。
"""
from __future__ import annotations

import pytest

from lib.wiring import to_json
from lib.wiring.passives import annotate_passives, _TOPO_DEFAULT_LOCATION


def _collect_passives(result: dict) -> list[dict]:
    out = []
    for info in result["wiring"].values():
        for pin in info.get("pins", []):
            if pin.get("passive"):
                out.append(pin["passive"])
        out.extend(info.get("decoupling", []))
    out.extend(result.get("power_passives", []))
    return out


class TestPassiveAnnotation:
    def test_passives_get_refdes_location_purchasable(self):
        r = to_json("Arduino", ["TempHumid", "LED_Single", "Light"])
        passives = _collect_passives(r)
        assert passives, "預期有被動元件被標註"
        for p in passives:
            assert "refdes" in p and p["refdes"][0] in "RCD"
            assert p["location"] in ("onboard", "external")
            assert p["purchasable"] == (p["location"] == "external")

    def test_topo_default_location(self):
        r = to_json("Arduino", ["TempHumid", "LED_Single", "Light"])
        by_topo = {}
        for p in _collect_passives(r):
            by_topo.setdefault(p.get("topo"), set()).add(p["location"])
        # 信號線被動(這三件 on_board 無對應) → external
        assert by_topo.get("pullup") == {"external"}, by_topo   # DHT22 4.7k
        assert by_topo.get("series") == {"external"}, by_topo   # LED 220
        assert by_topo.get("divider") == {"external"}, by_topo  # LDR 10k
        # MCU 電源軌 → onboard
        assert by_topo.get("bulk") == {"onboard"}, by_topo
        assert by_topo.get("decoupling", {"onboard"}) == {"onboard"}, by_topo

    def test_refdes_deterministic_and_no_pollution(self):
        # 同輸入兩次必得同 refdes（計數器重置 + 不污染共享模板/常數）
        r1 = to_json("Arduino", ["TempHumid", "LED_Single", "Light"])
        r2 = to_json("Arduino", ["TempHumid", "LED_Single", "Light"])
        rd1 = sorted(p["refdes"] for p in _collect_passives(r1))
        rd2 = sorted(p["refdes"] for p in _collect_passives(r2))
        assert rd1 == rd2, (rd1, rd2)
        # refdes 不重複（全方案一命名空間）
        assert len(rd1) == len(set(rd1)), rd1

    def test_passives_have_dual_end_nets(self):
        r = to_json("Arduino", ["TempHumid", "LED_Single", "Light"])
        for p in _collect_passives(r):
            nets = p.get("nets")
            assert isinstance(nets, list) and len(nets) == 2, (p.get("refdes"), nets)
            assert all(isinstance(n, str) and n for n in nets), nets
        # 拓撲 → 第二端正確
        for info in r["wiring"].values():
            for pin in info.get("pins", []):
                p = pin.get("passive")
                if not p:
                    continue
                if p["topo"] == "pullup":
                    assert p["nets"][1] == "VCC", p["nets"]
                elif p["topo"] == "divider":
                    assert p["nets"][1] == "GND", p["nets"]

    def test_power_passives_not_mutating_constant(self):
        # 連續呼叫不應讓 MCU_POWER_PASSIVES 累積 refdes / 數量爆增
        from lib.wiring.constants import MCU_POWER_PASSIVES
        before = len(MCU_POWER_PASSIVES["Arduino"])
        to_json("Arduino", ["LED_Single"])
        to_json("Arduino", ["LED_Single"])
        assert len(MCU_POWER_PASSIVES["Arduino"]) == before
        # 共享常數本身不被加 refdes
        assert all("refdes" not in p for p in MCU_POWER_PASSIVES["Arduino"])
