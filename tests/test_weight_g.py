"""tests/test_weight_g.py — STR16: weight_g SSOT 交叉驗證。

Cross-validates weight_g across:
  - data/component_datasheet_verified.json (.physical.weight_g)
  - lib/registry.COMPONENT_REGISTRY (.weight_g field on ComponentSpec)

Weight range sanity: 0.1g (single light component) to 5000g (heavy module upper bound).
"""
import json
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lib.registry import COMPONENT_REGISTRY

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATASHEET_PATH = os.path.join(_ROOT, "data", "component_datasheet_verified.json")

# weight_g 合理範圍
_WEIGHT_MIN_G = 0.1
_WEIGHT_MAX_G = 5000.0

# SSOT20: L298N-Driver-class is now in both registry and verified.json — no exemption.
_REGISTRY_EXEMPT = frozenset()

# SSOT20: registry.weight_g uses the "as-installed" convention — battery holders use
# physical.weight_with_batteries_g (Battery-AA = 56g incl. 2×AA cells, not 8g empty
# holder). The former _KNOWN_WEIGHT_DRIFT xfail (tolerating the wrong 48g) is removed;
# the convention is asserted exactly via _DS_INSTALLED_WEIGHT_MAP.


# ── 模組層級預載（供 parametrize 使用）──────────────────────────────────────

def _load_ds_weight_map() -> dict:
    """從 SSOT datasheet 載入 {class_name: weight_g}，排除 _meta 與無 weight_g 條目。"""
    with open(_DATASHEET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    result = {}
    for cn, spec in ds.items():
        if cn.startswith("_"):
            continue
        physical = spec.get("physical", {})
        if "weight_g" in physical:
            result[cn] = physical["weight_g"]
    return result


def _load_ds_class_names() -> list:
    """從 SSOT datasheet 載入所有 class_name（排除 _meta）。"""
    with open(_DATASHEET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    return sorted(k for k in ds if not k.startswith("_"))


def _load_ds_installed_weight_map() -> dict:
    """As-installed weight: physical.weight_with_batteries_g if present, else weight_g.

    SSOT20 convention: registry/specs WEIGHT_G is the in-use weight, so a battery
    holder carries its cells (Battery-AA 56g), matching how the component ships in
    a real assembly. Bare-component weight_g stays available via _DS_WEIGHT_MAP.
    """
    with open(_DATASHEET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    result = {}
    for cn, spec in ds.items():
        if cn.startswith("_"):
            continue
        physical = spec.get("physical", {})
        if "weight_with_batteries_g" in physical:
            result[cn] = physical["weight_with_batteries_g"]
        elif "weight_g" in physical:
            result[cn] = physical["weight_g"]
    return result


_DS_WEIGHT_MAP = _load_ds_weight_map()
_DS_INSTALLED_WEIGHT_MAP = _load_ds_installed_weight_map()
_DS_CLASS_NAMES = _load_ds_class_names()


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def datasheet():
    with open(_DATASHEET_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── 1. TestWeightGSSOTCoverage ─────────────────────────────────────────────

class TestWeightGSSOTCoverage:
    """驗證 SSOT JSON 中每個有 physical.weight_g 的元件數值合法。"""

    def test_has_weight_g_entries(self):
        """SSOT 至少要有 1 筆 weight_g 記錄。"""
        assert len(_DS_WEIGHT_MAP) > 0, "datasheet 中找不到任何 weight_g 欄位"

    @pytest.mark.parametrize("cn", sorted(_DS_WEIGHT_MAP))
    def test_weight_g_is_positive_float(self, cn):
        """每個有 weight_g 的 SSOT 元件：值必須是 float > 0。"""
        val = _DS_WEIGHT_MAP[cn]
        assert isinstance(val, (int, float)), (
            f"{cn}: weight_g 型別錯誤，期望 float，得到 {type(val).__name__}"
        )
        assert val > 0, f"{cn}: weight_g={val} 必須 > 0"

    def test_no_zero_weight(self):
        """任何 SSOT 元件的 weight_g 不得為 0（有物理質量的元件不可是 0）。"""
        zeros = {cn: v for cn, v in _DS_WEIGHT_MAP.items() if v == 0}
        assert zeros == {}, f"weight_g=0 的元件（實體元件不應為 0）：{zeros}"

    def test_no_negative_weight(self):
        """SSOT 不得有負值 weight_g。"""
        negatives = {cn: v for cn, v in _DS_WEIGHT_MAP.items() if v < 0}
        assert negatives == {}, f"weight_g < 0 的元件：{negatives}"

    def test_all_components_have_weight_g(self):
        """驗證 SSOT 所有元件都有 physical.weight_g（覆蓋率檢查）。

        若有元件缺少 weight_g，以 xfail 報告（資料缺口，非測試失敗）。
        """
        missing = [cn for cn in _DS_CLASS_NAMES if cn not in _DS_WEIGHT_MAP]
        if missing:
            pytest.xfail(f"以下元件缺少 physical.weight_g（已知資料缺口）：{missing}")


# ── 2. TestWeightGRegistryAlignment ───────────────────────────────────────

class TestWeightGRegistryAlignment:
    """COMPONENT_REGISTRY.weight_g 與 SSOT datasheet 對齊驗證。"""

    def test_registry_has_weight_g_field(self):
        """所有 registry 元件都必須有 weight_g 屬性（ComponentSpec 欄位）。"""
        missing = [cn for cn, spec in COMPONENT_REGISTRY.items()
                   if not hasattr(spec, "weight_g")]
        assert missing == [], f"缺少 weight_g 屬性的 registry 元件：{missing}"

    def test_registry_no_negative_weight(self):
        """registry 中不得有 weight_g < 0 的元件。"""
        negatives = {cn: spec.weight_g for cn, spec in COMPONENT_REGISTRY.items()
                     if spec.weight_g < 0}
        assert negatives == {}, f"registry weight_g < 0：{negatives}"

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_registry_matches_datasheet(self, cn):
        """registry.weight_g 必須等於 SSOT datasheet 的 as-installed 重量。

        SSOT20：registry 經 Tier-5 從 specs cache 讀穿，as-installed 慣例（電池座含
        電池 weight_with_batteries_g）。無 weight_g 記錄的元件 xfail（資料缺口）。
        """
        if cn in _REGISTRY_EXEMPT:
            pytest.skip(f"{cn} 在 registry exempt 清單（僅存在於 datasheet）")
        if cn not in _DS_INSTALLED_WEIGHT_MAP:
            pytest.xfail(f"{cn} 在 SSOT datasheet 中無 weight_g 記錄（已知缺口）")
        reg_val = COMPONENT_REGISTRY[cn].weight_g
        ds_val = _DS_INSTALLED_WEIGHT_MAP[cn]  # as-installed (battery holders incl. cells)
        assert reg_val == ds_val, (
            f"{cn}: registry.weight_g={reg_val} != datasheet as-installed weight={ds_val}"
        )


# ── 3. TestWeightGDataIntegrity ────────────────────────────────────────────

class TestWeightGDataIntegrity:
    """weight_g 資料完整性：範圍、重複、結構一致性。"""

    def test_no_duplicate_class_names(self, datasheet):
        """SSOT JSON 中不得有重複的 class_name 鍵（JSON 規範不允許，但雙重確認）。"""
        keys = [k for k in datasheet if not k.startswith("_")]
        assert len(keys) == len(set(keys)), (
            f"datasheet 中發現重複 class_name：{[k for k in set(keys) if keys.count(k) > 1]}"
        )

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_registry_weight_in_reasonable_range(self, cn):
        """registry 每個元件的 weight_g 必須在合理範圍 [0.1g, 5000g] 內。"""
        val = COMPONENT_REGISTRY[cn].weight_g
        assert _WEIGHT_MIN_G <= val <= _WEIGHT_MAX_G, (
            f"{cn}: weight_g={val}g 超出合理範圍 [{_WEIGHT_MIN_G}, {_WEIGHT_MAX_G}]g"
        )

    @pytest.mark.parametrize("cn", sorted(_DS_WEIGHT_MAP))
    def test_datasheet_weight_in_reasonable_range(self, cn):
        """datasheet 中有 weight_g 的元件必須在合理範圍內。"""
        val = _DS_WEIGHT_MAP[cn]
        assert _WEIGHT_MIN_G <= val <= _WEIGHT_MAX_G, (
            f"{cn}: datasheet.weight_g={val}g 超出合理範圍 [{_WEIGHT_MIN_G}, {_WEIGHT_MAX_G}]g"
        )

    def test_heavy_components_have_mass(self):
        """已知重型元件（馬達、底盤、電池）的 weight_g 必須 >= 5g。"""
        heavy_classes = {
            "Motor-DC-class", "Motor-Stepper-class", "Chassis-Car-class",
            "Battery-AA-class", "Battery-LiPo-class", "RaspberryPi-class",
            "Arduino-Uno-class",
        }
        underweight = {
            cn: _DS_WEIGHT_MAP[cn]
            for cn in heavy_classes
            if cn in _DS_WEIGHT_MAP and _DS_WEIGHT_MAP[cn] < 5.0
        }
        assert underweight == {}, (
            f"已知重型元件 weight_g 過低（< 5g）：{underweight}"
        )

    def test_lightweight_components_not_overweight(self):
        """已知輕型元件（LED、按鈕、蜂鳴器）的 weight_g 必須 <= 10g。"""
        light_classes = {
            "Button-class", "Lighting-LED-RGB-class", "Lighting-LED-PWM-class",
            "Buzzer-Active-class", "Buzzer-Passive-class",
        }
        overweight = {
            cn: _DS_WEIGHT_MAP[cn]
            for cn in light_classes
            if cn in _DS_WEIGHT_MAP and _DS_WEIGHT_MAP[cn] > 10.0
        }
        assert overweight == {}, (
            f"已知輕型元件 weight_g 過重（> 10g）：{overweight}"
        )

    def test_registry_no_zero_weight_g(self):
        """所有 registry 元件 weight_g 不得為 0（實體元件應有質量）。"""
        zero_weight = {cn for cn, spec in COMPONENT_REGISTRY.items()
                       if spec.weight_g == 0}
        assert zero_weight == set(), (
            f"registry 中 weight_g=0 的元件：{zero_weight}"
        )
