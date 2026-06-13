"""Phase 2 step 1：被動元件標註（refdes/location/purchasable）測試。

驗證 annotate_passives 與 to_json 接入:RefDes 確定性、location 拓撲判定、
purchasable 分流，以及「不污染共享模板/常數」（跨呼叫一致）。
"""
from __future__ import annotations

import pytest

import re

from lib.wiring import to_json
from lib.wiring.passives import (
    annotate_passives, _TOPO_DEFAULT_LOCATION, annotate_active_refdes,
)


def _pfx(refdes: str) -> str:
    """refdes 字母前綴(去尾數字),如 'K1'→'K'、'DS2'→'DS'。"""
    m = re.match(r"[A-Za-z]+", refdes or "")
    return m.group() if m else ""


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
        # 信號線被動 → external
        assert by_topo.get("pullup") == {"external"}, by_topo   # DHT22 4.7k
        assert by_topo.get("series") == {"external"}, by_topo   # LED 220
        # CCR3: LDR GL5528 carrier 分壓已板載 → 無外接 divider，
        # test_ldr_no_external_divider 已驗 passive=None，此處不斷言 divider
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


class TestActiveRefdes:
    """P3.2/G3:active 元件確定性 refdes(U/K/M/BT/DS/LS/SW),依真實 SSOT class 前綴。
    被動已有 R/C/D;此組鎖 active 元件 refdes 的確定性、型別前綴正確、唯一、序入 to_json。

    _COMPS 須為 Arduino UNO **腳位可行集**(digital/pwm 唯一需求 ≤ 12):原含 DCMotor
    時 13 > 12 鴿籠不可行,to_json 正確 raise PinAllocationError(過訂 gate 見
    test_csp_pin_allocation.py::TestGlobalPinBudget)。現集 10 需求,6 種前綴全覆蓋。"""

    _COMPS = ["Relay", "Pump", "Servo", "Stepper", "OLED", "LED_Single",
              "Buzzer_Active", "Button", "Switch", "SoilMoisture"]

    def test_refdes_serialized_into_to_json(self):
        """to_json 帶頂層 refdes map,且每周邊 wiring 條目帶 refdes(供 render badge)。"""
        r = to_json("Arduino", self._COMPS)
        rd = r.get("refdes")
        assert isinstance(rd, dict) and rd, "to_json 應序入非空 refdes map"
        for comp, info in r["wiring"].items():
            assert info.get("refdes") == rd.get(comp), f"{comp} wiring.refdes 與 map 不一致"

    def test_mcu_is_u1(self):
        """MCU(brain)依 IEEE 315 慣例取 U1。"""
        r = to_json("Arduino", self._COMPS)
        assert r["refdes"].get("Arduino") == "U1"
        r2 = to_json("ESP32", ["OLED", "Relay"])
        assert r2["refdes"].get("ESP32") == "U1"

    def test_type_prefixes_by_real_ssot_class(self):
        """型別前綴依**真實 SSOT class**:Relay→K、Motor/Pump→M、Lighting→DS、Buzzer→LS、
        Switch/Button→SW、IC/模組(MCU/OLED/感測)→U。"""
        rd = to_json("Arduino", self._COMPS)["refdes"]
        expect = {
            "Relay": "K",          # Relay-Module-class
            "Pump": "M", "Servo": "M", "Stepper": "M",   # Pump-Water / Motor-*
            "LED_Single": "DS",    # Lighting-LED-PWM-class
            "Buzzer_Active": "LS", # Buzzer-Active-class
            "Button": "SW", "Switch": "SW",
            "OLED": "U",           # Display-OLED-class(IC 模組)
            "SoilMoisture": "U",   # Sensor 模組
        }
        for comp, pfx in expect.items():
            assert _pfx(rd[comp]) == pfx, f"{comp} refdes={rd[comp]} 前綴應為 {pfx}"

    def test_dcmotor_driver_class_prefix_unit(self):
        """DCMotor(L298N-Driver-class)→ U(驅動 IC;真馬達是 net 上的負載端子)。
        以純函數測:含 DCMotor 的全集在 UNO 上腳位過訂,不可走 to_json。"""
        m = annotate_active_refdes({"DCMotor": {"pins": []}}, brain_short="Arduino")
        assert m["DCMotor"] == "U2", m   # U1=MCU,L298N 驅動 IC 取 U2

    def test_oled_not_misclassified_as_led(self):
        """回歸鎖:'OLED' 含子字串 'LED' 但**不可**誤判為 DS(Display-OLED 是 IC → U)。
        前綴須由真實 SSOT class('Display-OLED-class' 無 'Lighting')決定,非 short+'-class' 偽名。"""
        rd = to_json("Arduino", ["OLED", "LED_Single"])["refdes"]
        assert _pfx(rd["OLED"]) == "U", f"OLED 不應為 DS(實得 {rd['OLED']})"
        assert _pfx(rd["LED_Single"]) == "DS", "真 LED 仍應為 DS"

    def test_deterministic(self):
        """同輸入必得同 refdes map(確定性,可複現)。"""
        a = to_json("Arduino", self._COMPS)["refdes"]
        b = to_json("Arduino", self._COMPS)["refdes"]
        assert a == b

    def test_unique(self):
        """全 refdes 唯一(無兩元件撞號)。"""
        rd = to_json("Arduino", self._COMPS)["refdes"]
        vals = list(rd.values())
        assert len(vals) == len(set(vals)), f"refdes 重複:{vals}"

    def test_annotate_active_refdes_unit(self):
        """純函數:空 wiring + brain → 僅 U1;in-place 設 wiring[comp].refdes。"""
        assert annotate_active_refdes({}, brain_short="Arduino") == {"Arduino": "U1"}
        w = {"Relay": {"pins": []}}
        m = annotate_active_refdes(w, brain_short="Arduino")
        assert m == {"Arduino": "U1", "Relay": "K1"}
        assert w["Relay"]["refdes"] == "K1"
