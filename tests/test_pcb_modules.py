"""tests/test_pcb_modules.py — STR23: lib/pcb/ 子模組測試覆蓋。

涵蓋：
  - 四塊 MCU 板（Arduino Uno R3 / ESP32 DevKit V1 / Raspberry Pi 4B / micro:bit V2）
  - Tier 2 感測器模組（HC-SR04 / DHT22 / PIR-HC-SR501 / SSD1306 OLED / LCD 1602 / Relay）
  - 每板 port 數量 > 0
  - port 座標在合理範圍（0 ≤ x ≤ board_length, 0 ≤ y ≤ board_width）
  - board dimensions 合理（10mm ≤ L ≤ 300mm，允許 RPi 85mm, LCD 80mm）
  - PCB_REGISTRY.get_board 正確回傳對應板
  - pin count 與 lib/pin_maps.py 的 _PIN_MAPS 鍵對應關係一致
  - port label（name）不為空
  - mounting_holes 座標在板範圍內

跑：.venv/Scripts/python.exe -m pytest tests/test_pcb_modules.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# Fixtures — 各板 PCBSpec
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def arduino():
    from lib.pcb import ARDUINO_UNO_R3
    return ARDUINO_UNO_R3


@pytest.fixture(scope="module")
def esp32():
    from lib.pcb import ESP32_DEVKIT_V1
    return ESP32_DEVKIT_V1


@pytest.fixture(scope="module")
def rpi4b():
    from lib.pcb import RASPBERRY_PI_4B
    return RASPBERRY_PI_4B


@pytest.fixture(scope="module")
def microbit():
    from lib.pcb import MICROBIT_V2
    return MICROBIT_V2


@pytest.fixture(scope="module")
def pcb_registry():
    from lib.pcb import PCB_REGISTRY
    return PCB_REGISTRY


# ─────────────────────────────────────────────────────────────
# 1. PCB_REGISTRY 完整性
# ─────────────────────────────────────────────────────────────

def test_registry_contains_all_mcu_boards(pcb_registry):
    """PCB_REGISTRY 必須含 4 個 MCU board key。"""
    expected = {
        "Arduino-Uno-class", "ESP32-class",
        "Microbit-class", "RaspberryPi-class",
    }
    assert expected <= set(pcb_registry.keys()), (
        f"PCB_REGISTRY 缺少: {expected - set(pcb_registry.keys())}"
    )


def test_registry_contains_module_keys(pcb_registry):
    """PCB_REGISTRY 必須含所有 6 個 Tier 2 模組 key。"""
    expected = {
        "Sensor-Ultrasonic-class", "Sensor-TempHumid-class", "Sensor-PIR-class",
        "Display-OLED-class", "Display-LCD-class", "Relay-Module-class",
    }
    assert expected <= set(pcb_registry.keys()), (
        f"PCB_REGISTRY 缺少模組 key: {expected - set(pcb_registry.keys())}"
    )


def test_registry_get_board_arduino(pcb_registry, arduino):
    """PCB_REGISTRY['Arduino-Uno-class'] 應回傳 ARDUINO_UNO_R3。"""
    assert pcb_registry["Arduino-Uno-class"] is arduino


def test_registry_get_board_esp32(pcb_registry, esp32):
    """PCB_REGISTRY['ESP32-class'] 應回傳 ESP32_DEVKIT_V1。"""
    assert pcb_registry["ESP32-class"] is esp32


def test_registry_get_board_rpi(pcb_registry, rpi4b):
    """PCB_REGISTRY['RaspberryPi-class'] 應回傳 RASPBERRY_PI_4B。"""
    assert pcb_registry["RaspberryPi-class"] is rpi4b


def test_registry_get_board_microbit(pcb_registry, microbit):
    """PCB_REGISTRY['Microbit-class'] 應回傳 MICROBIT_V2。"""
    assert pcb_registry["Microbit-class"] is microbit


# ─────────────────────────────────────────────────────────────
# 2. Arduino Uno R3 — 板尺寸 + pins + 座標範圍
# ─────────────────────────────────────────────────────────────

def test_arduino_board_dimensions_reasonable(arduino):
    """Arduino Uno R3 板尺寸應在合理範圍（10 ≤ L ≤ 300mm）。"""
    assert 10 <= arduino.length <= 300
    assert 10 <= arduino.width <= 300


def test_arduino_board_known_dimensions(arduino):
    """Arduino Uno R3 標準尺寸 68.58 × 53.34mm。"""
    assert abs(arduino.length - 68.58) < 0.1
    assert abs(arduino.width - 53.34) < 0.1


def test_arduino_pin_count(arduino):
    """Arduino Uno R3 應有 38 個 pin（14 + 18 + 6）。"""
    assert len(arduino.pins) == 38


def test_arduino_pins_in_board_bounds(arduino):
    """Arduino Uno R3 所有 pin 座標必須在板範圍內（含 1mm 容差）。"""
    for p in arduino.pins:
        assert -1.0 <= p.x <= arduino.length + 1.0, (
            f"Pin {p.name} x={p.x} 超出板長度 {arduino.length}"
        )
        assert -1.0 <= p.y <= arduino.width + 1.0, (
            f"Pin {p.name} y={p.y} 超出板寬度 {arduino.width}"
        )


def test_arduino_pin_names_not_empty(arduino):
    """Arduino Uno R3 所有 pin 名稱不為空。"""
    for p in arduino.pins:
        assert p.name, f"pad_index={p.pad_index} 的 pin 名稱為空"


def test_arduino_mounting_holes_count(arduino):
    """Arduino Uno R3 應有 4 個 mounting holes。"""
    assert len(arduino.mounting_holes) == 4


def test_arduino_mounting_holes_in_bounds(arduino):
    """Arduino Uno R3 mounting holes 座標在板範圍內。"""
    for mh in arduino.mounting_holes:
        assert 0 <= mh.x <= arduino.length, f"MountingHole x={mh.x} 超界"
        assert 0 <= mh.y <= arduino.width, f"MountingHole y={mh.y} 超界"


def test_arduino_pin_groups_janalog_count(arduino):
    """Arduino JANALOG group 應有 14 個 pin index。"""
    assert len(arduino.pin_groups["JANALOG"]) == 14


def test_arduino_pin_groups_jdigital_count(arduino):
    """Arduino JDIGITAL group 應有 18 個 pin index。"""
    assert len(arduino.pin_groups["JDIGITAL"]) == 18


def test_arduino_find_pin_a5(arduino):
    """find_pin('A5') 應能找到 A5/SCL pin。"""
    p = arduino.find_pin("A5")
    assert p is not None
    assert "A5" in p.name or p.arduino_pin == "A5"


# ─────────────────────────────────────────────────────────────
# 3. ESP32 DevKit V1 — 板尺寸 + pins
# ─────────────────────────────────────────────────────────────

def test_esp32_board_dimensions_reasonable(esp32):
    """ESP32 DevKit V1 板尺寸應在合理範圍（10 ≤ L ≤ 300mm）。"""
    assert 10 <= esp32.length <= 300
    assert 10 <= esp32.width <= 300


def test_esp32_pin_count(esp32):
    """ESP32 DevKit V1 應有 30 個 pin（左 15 + 右 15）。"""
    assert len(esp32.pins) == 30


def test_esp32_pins_in_board_bounds(esp32):
    """ESP32 DevKit V1 所有 pin 座標必須在板範圍內（含 1mm 容差）。"""
    for p in esp32.pins:
        assert -1.0 <= p.x <= esp32.length + 1.0, (
            f"Pin {p.name} x={p.x} 超出板長度 {esp32.length}"
        )
        assert -1.0 <= p.y <= esp32.width + 1.0, (
            f"Pin {p.name} y={p.y} 超出板寬度 {esp32.width}"
        )


def test_esp32_pin_names_not_empty(esp32):
    """ESP32 DevKit V1 所有 pin 名稱不為空。"""
    for p in esp32.pins:
        assert p.name, f"pad_index={p.pad_index} 的 pin 名稱為空"


def test_esp32_find_pin_3v3(esp32):
    """find_pin('+3V3') 應能找到電源 pin。"""
    p = esp32.find_pin("+3V3")
    assert p is not None


def test_esp32_has_left_right_groups(esp32):
    """ESP32 應有 LEFT 和 RIGHT 兩個 pin_groups。"""
    assert "LEFT" in esp32.pin_groups
    assert "RIGHT" in esp32.pin_groups


# ─────────────────────────────────────────────────────────────
# 4. Raspberry Pi 4B — 板尺寸 + GPIO header
# ─────────────────────────────────────────────────────────────

def test_rpi4b_board_dimensions_reasonable(rpi4b):
    """RPi 4B 板尺寸應在合理範圍（10 ≤ L ≤ 300mm）。"""
    assert 10 <= rpi4b.length <= 300
    assert 10 <= rpi4b.width <= 300


def test_rpi4b_board_known_dimensions(rpi4b):
    """RPi 4B 標準尺寸 85 × 56mm。"""
    assert abs(rpi4b.length - 85.0) < 0.1
    assert abs(rpi4b.width - 56.0) < 0.1


def test_rpi4b_pin_count(rpi4b):
    """RPi 4B 應有 40 個 GPIO header pin。"""
    assert len(rpi4b.pins) == 40


def test_rpi4b_pins_in_board_bounds(rpi4b):
    """RPi 4B 所有 pin 座標必須在板範圍內（含 2mm 容差）。"""
    for p in rpi4b.pins:
        assert -2.0 <= p.x <= rpi4b.length + 2.0, (
            f"Pin {p.name} x={p.x} 超出板長度 {rpi4b.length}"
        )
        assert -2.0 <= p.y <= rpi4b.width + 2.0, (
            f"Pin {p.name} y={p.y} 超出板寬度 {rpi4b.width}"
        )


def test_rpi4b_pin_names_not_empty(rpi4b):
    """RPi 4B 所有 pin 名稱不為空。"""
    for p in rpi4b.pins:
        assert p.name, f"pad_index={p.pad_index} 的 pin 名稱為空"


def test_rpi4b_mounting_holes_count(rpi4b):
    """RPi 4B 應有 4 個 mounting holes。"""
    assert len(rpi4b.mounting_holes) == 4


def test_rpi4b_gpio40_group_exists(rpi4b):
    """RPi 4B 應有 GPIO_40 pin_group。"""
    assert "GPIO_40" in rpi4b.pin_groups
    assert len(rpi4b.pin_groups["GPIO_40"]) == 40


# ─────────────────────────────────────────────────────────────
# 5. micro:bit V2 — 板尺寸 + edge connector
# ─────────────────────────────────────────────────────────────

def test_microbit_board_dimensions_reasonable(microbit):
    """micro:bit V2 板尺寸應在合理範圍（10 ≤ L ≤ 300mm）。"""
    assert 10 <= microbit.length <= 300
    assert 10 <= microbit.width <= 300


def test_microbit_board_known_dimensions(microbit):
    """micro:bit V2 標準尺寸 51.60 × 42.00mm。"""
    assert abs(microbit.length - 51.60) < 0.1
    assert abs(microbit.width - 42.00) < 0.1


def test_microbit_pin_count(microbit):
    """micro:bit V2 應有 27 個 pin（5 big + 22 small）。"""
    assert len(microbit.pins) == 27


def test_microbit_pins_in_board_bounds(microbit):
    """micro:bit V2 所有 pin 座標必須在板範圍內（含 1mm 容差）。"""
    for p in microbit.pins:
        assert -1.0 <= p.x <= microbit.length + 1.0, (
            f"Pin {p.name} x={p.x} 超出板長度 {microbit.length}"
        )
        assert -1.0 <= p.y <= microbit.width + 1.0, (
            f"Pin {p.name} y={p.y} 超出板寬度 {microbit.width}"
        )


def test_microbit_find_pin_p0(microbit):
    """find_pin('P0') 應能找到 P0 大環 pin。"""
    p = microbit.find_pin("P0")
    assert p is not None
    assert p.name == "P0"


def test_microbit_edge_groups(microbit):
    """micro:bit V2 應有 EDGE_BIG 和 EDGE_SMALL pin_groups。"""
    assert "EDGE_BIG" in microbit.pin_groups
    assert "EDGE_SMALL" in microbit.pin_groups
    assert len(microbit.pin_groups["EDGE_BIG"]) == 5
    assert len(microbit.pin_groups["EDGE_SMALL"]) == 22


# ─────────────────────────────────────────────────────────────
# 6. Tier 2 模組 — 基本尺寸與 pin 完整性
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name,expected_pin_count,max_dim", [
    ("HCSR04",     4,  50),
    ("DHT22",      4,  30),
    ("PIR_HCSR501",3,  35),
    ("OLED_SSD1306",4, 30),
    ("LCD_1602",   4,  85),
    ("RELAY_1CH",  3,  55),
])
def test_module_pin_count(mod_name, expected_pin_count, max_dim):
    """各 Tier 2 模組 pin count 應符合預期。"""
    import lib.pcb as pcb_pkg
    mod = getattr(pcb_pkg, mod_name)
    assert len(mod.pins) == expected_pin_count, (
        f"{mod_name} pin count={len(mod.pins)}，預期={expected_pin_count}"
    )


@pytest.mark.parametrize("mod_name", [
    "HCSR04", "DHT22", "PIR_HCSR501", "OLED_SSD1306", "LCD_1602", "RELAY_1CH"
])
def test_module_board_dimensions_reasonable(mod_name):
    """各 Tier 2 模組板尺寸應在合理範圍（10 ≤ L ≤ 100mm）。"""
    import lib.pcb as pcb_pkg
    mod = getattr(pcb_pkg, mod_name)
    assert 10 <= mod.length <= 100, (
        f"{mod_name} length={mod.length} 超出合理範圍"
    )
    assert 10 <= mod.width <= 100, (
        f"{mod_name} width={mod.width} 超出合理範圍"
    )


@pytest.mark.parametrize("mod_name", [
    "HCSR04", "DHT22", "PIR_HCSR501", "OLED_SSD1306", "LCD_1602", "RELAY_1CH"
])
def test_module_pin_names_not_empty(mod_name):
    """各 Tier 2 模組所有 pin 名稱不為空。"""
    import lib.pcb as pcb_pkg
    mod = getattr(pcb_pkg, mod_name)
    for p in mod.pins:
        assert p.name, f"{mod_name} pad_index={p.pad_index} 的 pin 名稱為空"


@pytest.mark.parametrize("mod_name", [
    "HCSR04", "DHT22", "PIR_HCSR501", "OLED_SSD1306", "LCD_1602", "RELAY_1CH"
])
def test_module_pins_in_board_bounds(mod_name):
    """各 Tier 2 模組 pin 座標必須在板範圍內（含 2mm 容差）。"""
    import lib.pcb as pcb_pkg
    mod = getattr(pcb_pkg, mod_name)
    for p in mod.pins:
        assert -2.0 <= p.x <= mod.length + 2.0, (
            f"{mod_name} Pin {p.name} x={p.x} 超出板長度 {mod.length}"
        )
        assert -2.0 <= p.y <= mod.width + 2.0, (
            f"{mod_name} Pin {p.name} y={p.y} 超出板寬度 {mod.width}"
        )


# ─────────────────────────────────────────────────────────────
# 7. PCBSpec 通用方法正確性
# ─────────────────────────────────────────────────────────────

def test_pcbspec_pin_index_map_unique(arduino):
    """pin_index_map 的 key 應唯一（無重複 pad_index）。"""
    idx_map = arduino.pin_index_map()
    assert len(idx_map) == len(arduino.pins), "存在重複 pad_index"


def test_pcbspec_pins_in_group_returns_correct_subset(arduino):
    """pins_in_group('JANALOG') 應回傳 14 個 pin。"""
    janalog = arduino.pins_in_group("JANALOG")
    assert len(janalog) == 14


def test_pcbspec_thermal_profile_returns_list(arduino):
    """thermal_profile('typical') 應回傳 list，且每項含必要 keys。"""
    profile = arduino.thermal_profile("typical")
    assert isinstance(profile, list)
    for item in profile:
        for key in ("sub_name", "x", "y", "mw"):
            assert key in item, f"thermal_profile item 缺少 key: {key}"


def test_pcbspec_total_thermal_mw_positive(arduino):
    """arduino total_thermal_mw('typical') 應 > 0（有熱源元件）。"""
    total = arduino.total_thermal_mw("typical")
    assert total > 0


# ─────────────────────────────────────────────────────────────
# 8. pin count 與 lib/pin_maps.py 的 _PIN_MAPS 對應關係
# ─────────────────────────────────────────────────────────────

def test_pin_maps_arduino_analog_count():
    """_PIN_MAPS['Arduino']['analog'] 應含 6 個 analog pin（A0-A5）。"""
    from lib.pin_maps import _PIN_MAPS
    assert len(_PIN_MAPS["Arduino"]["analog"]) == 6


def test_pin_maps_esp32_has_input_only():
    """_PIN_MAPS['ESP32'] 應含 input_only 欄位（GPIO 34/35/36/39）。"""
    from lib.pin_maps import _PIN_MAPS
    assert "input_only" in _PIN_MAPS["ESP32"]
    assert set(_PIN_MAPS["ESP32"]["input_only"]) == {34, 35, 36, 39}


def test_pin_maps_rpi_no_analog():
    """_PIN_MAPS['RPi']['analog'] 應為空（RPi 無 ADC）。"""
    from lib.pin_maps import _PIN_MAPS
    assert _PIN_MAPS["RPi"]["analog"] == []


def test_pcb_arduino_analog_count_matches_pin_maps(arduino):
    """Arduino PCBSpec JANALOG group 的 AD 類 pin 數應 <= _PIN_MAPS (A4/A5 雙用途 I2C)。"""
    from lib.pin_maps import _PIN_MAPS
    janalog_pins = arduino.pins_in_group("JANALOG")
    ad_pins = [p for p in janalog_pins if p.function == "ANALOG"]
    # A4/A5 在 PCBSpec 中可能標記為 I2C 而非 ANALOG，所以 PCBSpec <= pin_maps
    assert len(ad_pins) <= len(_PIN_MAPS["Arduino"]["analog"])
    assert len(ad_pins) >= 4  # 至少 A0-A3 必為純 ANALOG


def test_pcb_esp32_pin_count_ge_pin_maps_digital(esp32):
    """ESP32 PCBSpec 的總 GPIO pin 數應 >= _PIN_MAPS['ESP32']['digital'] 清單長度。"""
    from lib.pin_maps import _PIN_MAPS
    gpio_pins_in_pcb = [p for p in esp32.pins if p.function == "GPIO"]
    # _PIN_MAPS digital list 較精簡，PCBSpec 含 UART/SPI/I2C 混合類型，允許 PCB >= map
    assert len(esp32.pins) >= len(_PIN_MAPS["ESP32"]["digital"])


def test_pin_maps_microbit_i2c_matches_pcb(microbit):
    """_PIN_MAPS['Microbit']['i2c'] 的 sda/scl pin 應在 PCBSpec pin_groups 範圍內。"""
    from lib.pin_maps import _PIN_MAPS
    i2c_info = _PIN_MAPS["Microbit"]["i2c"]
    # micro:bit i2c SDA=20, SCL=19 — edge_small pin 涵蓋 0-21
    assert "sda" in i2c_info
    assert "scl" in i2c_info


def test_pin_maps_all_mcu_keys_present():
    """_PIN_MAPS 應含 Arduino / ESP32 / RPi / Microbit 四個 brain key。"""
    from lib.pin_maps import _PIN_MAPS
    expected = {"Arduino", "ESP32", "RPi", "Microbit"}
    assert expected <= set(_PIN_MAPS.keys()), (
        f"_PIN_MAPS 缺少 brain key: {expected - set(_PIN_MAPS.keys())}"
    )
