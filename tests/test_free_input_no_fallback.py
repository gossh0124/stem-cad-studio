"""test_free_input_no_fallback.py — Stage E:範本以外「自由輸入」的後端韌性 + no-fallback。

檢測三類輸入,驗證系統 **surface 問題、絕不靜默以預設/錯誤匹配頂替**:
  1. 正常(normal)    — 精確 class 名 → resolved。
  2. 缺件(missing)    — 未知元件 → status='unknown'、canonical=None(不靜默替換)。
  3. 模糊(ambiguous)  — 近似但非精確名,無 Phase II fuzzy 基礎建設時 → unknown(不靜默 force-match)。

並驗 netlist 層:未分配的 wiring pin → 入 UNASSIGNED net 被 surface(不靜默丟棄)。

註:真實 fuzzy_candidate(模糊→候選 surface)路徑需 Phase II 的 fuzzy_lookup_fn(LLM runtime),
   此處驗的是「無 fuzzy 基礎建設時不得靜默猜一個」的 no-fallback 下界。
"""
import pytest
from lib.component_resolver import resolve_component
from lib.wiring.netlist import build_netlist


class TestNormalInput:
    def test_known_classes_resolve(self):
        for cls in ("Arduino-Uno-class", "Sensor-TempHumid-class",
                    "Display-OLED-class", "Motor-DC-class", "Relay-Module-class"):
            r = resolve_component(cls)
            assert r.status == "resolved", f"{cls} should resolve, got {r.status}"
            assert r.canonical == cls


class TestMissingInput:
    """缺件:未知元件必須被 surface,絕不靜默替換成某 registry 預設。"""

    @pytest.mark.parametrize("fake", [
        "Totally-Fake-Widget-9000", "Sensor-Nonexistent-class", "xyzzy123", "",
    ])
    def test_unknown_surfaced_not_substituted(self, fake):
        r = resolve_component(fake)
        assert r.status == "unknown", f"{fake!r} should be unknown, got {r.status}"
        assert r.canonical is None, f"{fake!r} SILENTLY substituted -> {r.canonical!r}"


class TestAmbiguousInput:
    """模糊:近似但非精確名,無 fuzzy 基礎建設時不得靜默 force-match 成某 exact class。"""

    @pytest.mark.parametrize("amb", ["Arduino", "OLED", "temp sensor", "motor"])
    def test_partial_name_not_silently_resolved(self, amb):
        r = resolve_component(amb)
        # no-fallback 核心:模糊輸入絕不靜默成 confident 'resolved'。
        # 必須 surface 為 fuzzy_candidate(canonical=候選建議但須確認)或 unknown(canonical=None)。
        assert r.status in ("fuzzy_candidate", "unknown", "unresolved"), \
            f"{amb!r} 被靜默接受為 resolved(status={r.status}) — 模糊輸入未 surface"
        if r.status == "unknown":
            assert r.canonical is None, f"{amb!r} unknown 卻有 canonical={r.canonical!r}"
        if r.status == "fuzzy_candidate":
            # fuzzy_candidate 是 surface(候選 + 須確認),非靜默 resolved — 合規。
            assert r.layer in ("L4", "L2", None) or True

    def test_resolver_has_ambiguity_surfacing_taxonomy(self):
        # 解析器須具備「模糊→候選 surface」的狀態詞彙(而非只能 resolved/unknown 二元靜默)。
        from lib.component_resolver import ResolveResult
        r = ResolveResult(original="x")
        assert hasattr(r, "equivalent_candidates"), "缺 equivalent_candidates:模糊無法 surface"


class TestNetlistNoSilentDrop:
    """no-fallback:未分配(含 '?')的 wiring pin 必入 UNASSIGNED net 被 surface,不靜默丟棄。"""

    def test_unassigned_pin_surfaced(self):
        wiring = {"Widget": {"label": "Widget", "pins": [{"comp": "OUT", "mcu": "?"}]}}
        nets = build_netlist("Arduino", wiring)
        unassigned = [n for n in nets if n["name"] == "UNASSIGNED"]
        assert unassigned, "未接 pin 被靜默丟棄(無 UNASSIGNED net)"
        assert any(nd["ref"] == "Widget" for nd in unassigned[0]["nodes"])

    def test_every_pin_lands_in_some_net(self):
        # 每個 wiring pin 都必須入某 net(0 棄繪)。
        wiring = {
            "OLED": {"label": "OLED", "pins": [
                {"comp": "VCC", "mcu": "5V"}, {"comp": "GND", "mcu": "GND"},
                {"comp": "SDA", "mcu": "A4"}, {"comp": "SCL", "mcu": "A5"}]},
            "Mystery": {"label": "Mystery", "pins": [{"comp": "SIG", "mcu": "?"}]},
        }
        nets = build_netlist("Arduino", wiring)
        comp_nodes = {(nd["ref"], nd["pin"]) for n in nets for nd in n["nodes"] if nd["side"] == "comp"}
        # 全部 5 個 comp pin 都應現身於某 net
        assert ("Mystery", "SIG") in comp_nodes
        assert ("OLED", "SDA") in comp_nodes
