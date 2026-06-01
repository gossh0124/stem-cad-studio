"""tests/test_wiring.py — STR19: wiring 核心接線邏輯測試。

覆蓋：normalize_comp, normalize_brain, normalize_comps,
     allocate_pins, resolve_wiring, to_json
"""
from __future__ import annotations
import pytest

from lib.wiring import (
    COMP_PIN_NEEDS,
    PIN_POOLS,
    WIRING_TEMPLATES,
    allocate_pins,
    normalize_brain,
    normalize_comp,
    normalize_comps,
    resolve_wiring,
    to_json,
)
from lib.pin_maps import _PIN_MAPS


# ── normalize_comp ───────────────────────────────────────────

class TestNormalizeComp:
    def test_direct_match(self):
        assert normalize_comp("NeoPixel") == "NeoPixel"
        assert normalize_comp("Servo") == "Servo"

    def test_strip_class_suffix(self):
        assert normalize_comp("NeoPixel-class") == "NeoPixel"

    def test_taxonomy_mapping(self):
        assert normalize_comp("Sensor-SoilMoisture") == "SoilMoisture"
        assert normalize_comp("Lighting-NeoPixel") == "NeoPixel"
        assert normalize_comp("Lighting-LED-PWM") == "LED_Single"
        assert normalize_comp("Motor-Servo") == "Servo"
        assert normalize_comp("Motor-DC") == "DCMotor"
        assert normalize_comp("Buzzer-Active") == "Buzzer_Active"
        assert normalize_comp("Display-OLED") == "OLED"

    def test_unknown_passthrough(self):
        assert normalize_comp("UnknownThing") == "UnknownThing"

    def test_class_then_taxonomy(self):
        assert normalize_comp("Sensor-SoilMoisture-class") == "SoilMoisture"


# ── normalize_brain ──────────────────────────────────────────

class TestNormalizeBrain:
    def test_direct_pool_match(self):
        assert normalize_brain("Arduino") == "Arduino"
        assert normalize_brain("ESP32") == "ESP32"
        assert normalize_brain("Microbit") == "Microbit"
        assert normalize_brain("RPi") == "RPi"

    def test_taxonomy_mapping(self):
        assert normalize_brain("Arduino-Uno") == "Arduino"
        assert normalize_brain("Arduino-Nano") == "Arduino"
        assert normalize_brain("ESP8266") == "ESP32"
        assert normalize_brain("RaspberryPi") == "RPi"

    def test_class_suffix(self):
        assert normalize_brain("Arduino-Uno-class") == "Arduino"

    def test_fuzzy_esp(self):
        assert normalize_brain("ESP32-S3") == "ESP32"

    def test_fuzzy_microbit(self):
        assert normalize_brain("Micro:bit-v2") == "Microbit"

    def test_fuzzy_rpi(self):
        assert normalize_brain("RPi-Pico") == "RPi"
        assert normalize_brain("RaspberryPi-4B") == "RPi"

    def test_fallback_arduino(self):
        assert normalize_brain("UnknownMCU") == "Arduino"


# ── normalize_comps ──────────────────────────────────────────

class TestNormalizeComps:
    def test_dedup(self):
        result = normalize_comps(["NeoPixel", "NeoPixel"])
        assert result == ["NeoPixel"]

    def test_preserves_order(self):
        result = normalize_comps(["Motor-Servo", "Sensor-PIR", "Lighting-NeoPixel"])
        assert result == ["Servo", "PIR", "NeoPixel"]

    def test_empty(self):
        assert normalize_comps([]) == []

    def test_mixed_dedup(self):
        result = normalize_comps(["Lighting-NeoPixel", "NeoPixel"])
        assert result == ["NeoPixel"]

    def test_strips_duplicate_after_normalize(self):
        result = normalize_comps(["Lighting-LED-Strip", "Lighting-NeoPixel"])
        assert result == ["NeoPixel"]


# ── allocate_pins ────────────────────────────────────────────

class TestAllocatePins:
    def test_single_component(self):
        result = allocate_pins("Arduino", ["SoilMoisture"])
        alloc = result["allocation"]
        assert "SoilMoisture" in alloc
        assert alloc["SoilMoisture"]["AO"] == "A0"

    def test_pin_labels_format(self):
        result = allocate_pins("Arduino", ["SoilMoisture"])
        assert "AO=A0" in result["pin_labels"]["SoilMoisture"]

    def test_multiple_components(self):
        result = allocate_pins("Arduino", ["NeoPixel", "Servo", "Button"])
        alloc = result["allocation"]
        assert len(alloc) == 3
        pins_used = set()
        for comp_pins in alloc.values():
            for pin in comp_pins.values():
                pins_used.add(str(pin))
        assert len(pins_used) == 3

    def test_i2c_shared(self):
        result = allocate_pins("Arduino", ["OLED"])
        alloc = result["allocation"]["OLED"]
        assert alloc["SDA"] == "A4"
        assert alloc["SCL"] == "A5"

    def test_pwm_fallback_to_digital(self):
        many_pwm = ["Servo"] * 10
        result = allocate_pins("Arduino", many_pwm)
        alloc = result["allocation"]
        assert "Servo" in alloc

    def test_unknown_component_skipped(self):
        result = allocate_pins("Arduino", ["NonExistent"])
        assert result["allocation"] == {}

    def test_auto_brain(self):
        result = allocate_pins("auto", ["NeoPixel"])
        assert "NeoPixel" in result["allocation"]

    def test_esp32_pins(self):
        result = allocate_pins("ESP32", ["NeoPixel"])
        pin = result["allocation"]["NeoPixel"]["DIN"]
        assert pin in PIN_POOLS["ESP32"]["digital"]

    def test_microbit_prefix(self):
        result = allocate_pins("Microbit", ["Button"])
        label = result["pin_labels"]["Button"]
        assert "P" in label


# ── resolve_wiring ───────────────────────────────────────────

class TestResolveWiring:
    def test_basic_structure(self):
        result = resolve_wiring("Arduino", ["SoilMoisture"])
        assert "SoilMoisture" in result
        pins = result["SoilMoisture"]["pins"]
        comp_names = [p["comp"] for p in pins]
        assert "GND" in comp_names
        assert "AO" in comp_names

    def test_vcc_injection(self):
        result = resolve_wiring("Arduino", ["NeoPixel"])
        pins = result["NeoPixel"]["pins"]
        vcc_pins = [p for p in pins if p["comp"] == "VCC"]
        assert len(vcc_pins) == 1
        assert vcc_pins[0]["mcu"] == "5V"

    def test_gnd_always_present(self):
        for comp_name in ["NeoPixel", "SoilMoisture", "Button", "Servo"]:
            result = resolve_wiring("Arduino", [comp_name])
            if comp_name not in result:
                continue
            pins = result[comp_name]["pins"]
            gnd_pins = [p for p in pins if p["comp"] == "GND"]
            assert len(gnd_pins) >= 1, f"{comp_name} missing GND"

    def test_label_present(self):
        result = resolve_wiring("Arduino", ["Servo"])
        assert "label" in result["Servo"]
        assert len(result["Servo"]["label"]) > 0

    def test_fixed_pin_not_allocated(self):
        result = resolve_wiring("Arduino", ["Speaker"])
        pins = result["Speaker"]["pins"]
        fixed = [p for p in pins if p["mcu"] == "SPK"]
        assert len(fixed) == 1


# ── to_json (integration) ───────────────────────────────────

class TestToJson:
    def test_keys(self):
        result = to_json("Arduino", ["NeoPixel", "Servo"])
        assert "brain" in result
        assert "allocation" in result
        assert "pin_labels" in result
        assert "wiring" in result
        assert "validation" in result

    def test_brain_normalized(self):
        result = to_json("Arduino-Uno-class", ["Servo"])
        assert result["brain"] == "Arduino"

    def test_taxonomy_input(self):
        result = to_json("Arduino-Uno-class",
                         ["Sensor-SoilMoisture", "Motor-Servo"])
        assert "SoilMoisture" in result["allocation"]
        assert "Servo" in result["allocation"]

    def test_validation_list(self):
        result = to_json("Arduino", ["NeoPixel"])
        assert isinstance(result["validation"], list)


# ── Data consistency ─────────────────────────────────────────

class TestDataConsistency:
    def test_all_pin_needs_have_templates(self):
        # SPI/UART 元件無需 wiring template（透過 bus 連接，非 per-pin 接線圖）
        no_template = {"Pump", "SD_Card", "GPS_Module", "Bluetooth_HC05"}
        for comp in COMP_PIN_NEEDS:
            if comp in no_template:
                continue
            assert comp in WIRING_TEMPLATES, (
                f"{comp} in COMP_PIN_NEEDS but missing from WIRING_TEMPLATES")

    def test_all_templates_have_pin_needs_or_are_pump(self):
        for comp in WIRING_TEMPLATES:
            if comp == "Pump":
                continue
            assert comp in COMP_PIN_NEEDS, (
                f"{comp} in WIRING_TEMPLATES but missing from COMP_PIN_NEEDS")

    def test_all_pools_have_i2c(self):
        for brain, pool in PIN_POOLS.items():
            assert "i2c" in pool, f"{brain} missing i2c pool"
            assert "sda" in pool["i2c"]
            assert "scl" in pool["i2c"]


# ── _PIN_MAPS 結構驗證 ────────────────────────────────────────

class TestPinMapsStructure:
    """GA-C2：驗證 _PIN_MAPS 包含 4 MCU 的完整 GPIO map。"""

    def test_all_four_mcus_present(self):
        """_PIN_MAPS 必須包含全部 4 款 MCU。"""
        assert set(_PIN_MAPS.keys()) == {"Arduino", "ESP32", "RPi", "Microbit"}

    def test_all_mcus_have_spi(self):
        """每個 MCU 的 map 都有 spi 欄位（Microbit 無 ss，但仍有 mosi/miso/sck）。"""
        for brain, m in _PIN_MAPS.items():
            assert "spi" in m, f"{brain} missing spi"
            assert "mosi" in m["spi"], f"{brain}.spi missing mosi"
            assert "miso" in m["spi"], f"{brain}.spi missing miso"
            assert "sck"  in m["spi"], f"{brain}.spi missing sck"

    def test_arduino_and_esp32_have_uart(self):
        """Arduino / ESP32 / RPi 都有 uart 欄位（Microbit 無硬體 UART 腳）。"""
        for brain in ("Arduino", "ESP32", "RPi"):
            m = _PIN_MAPS[brain]
            assert "uart" in m, f"{brain} missing uart"
            assert "tx" in m["uart"], f"{brain}.uart missing tx"
            assert "rx" in m["uart"], f"{brain}.uart missing rx"

    def test_esp32_has_input_only_list(self):
        """ESP32 map 應有 input_only 清單，且包含 34/35/36/39。"""
        io = _PIN_MAPS["ESP32"].get("input_only", [])
        assert set(io) >= {34, 35, 36, 39}

    def test_pin_pools_alias_matches_pin_maps(self):
        """PIN_POOLS 是 _PIN_MAPS 的子集 alias，pwm/digital/analog/i2c 必須一致。"""
        for brain in _PIN_MAPS:
            pool = PIN_POOLS[brain]
            m = _PIN_MAPS[brain]
            assert pool["pwm"]     == m["pwm"]
            assert pool["digital"] == m["digital"]
            assert pool["analog"]  == m["analog"]
            assert pool["i2c"]     == m["i2c"]


# ── SPI 分配測試 ──────────────────────────────────────────────

class TestSPIAllocation:
    """GA-C2：SPI 元件的 pin 分配。"""

    def test_sd_card_arduino_gets_spi_pins(self):
        """SD_Card 在 Arduino 上應分配到 SPI 硬體腳（SS=10, MOSI=11, MISO=12, SCK=13）。"""
        result = allocate_pins("Arduino", ["SD_Card"], use_spi=True)
        alloc = result["allocation"]["SD_Card"]
        spi = _PIN_MAPS["Arduino"]["spi"]
        assert alloc["MOSI"] == spi["mosi"]
        assert alloc["MISO"] == spi["miso"]
        assert alloc["SCK"]  == spi["sck"]
        assert alloc["SS"]   == spi["ss"]

    def test_sd_card_esp32_gets_spi_pins(self):
        """SD_Card 在 ESP32 上應分配到 SPI 硬體腳。"""
        result = allocate_pins("ESP32", ["SD_Card"], use_spi=True)
        alloc = result["allocation"]["SD_Card"]
        spi = _PIN_MAPS["ESP32"]["spi"]
        assert alloc["MOSI"] == spi["mosi"]
        assert alloc["MISO"] == spi["miso"]
        assert alloc["SCK"]  == spi["sck"]

    def test_sd_card_returns_pin_labels(self):
        """allocate_pins 對 SD_Card 要回傳 pin_labels。"""
        result = allocate_pins("Arduino", ["SD_Card"], use_spi=True)
        label = result["pin_labels"].get("SD_Card", "")
        assert "MOSI=" in label
        assert "SCK="  in label


# ── UART 分配測試 ─────────────────────────────────────────────

class TestUARTAllocation:
    """GA-C2：UART 元件的 pin 分配。"""

    def test_gps_arduino_gets_uart_pins(self):
        """GPS_Module 在 Arduino 上應分配 UART tx/rx。"""
        result = allocate_pins("Arduino", ["GPS_Module"], use_uart=True)
        alloc = result["allocation"]["GPS_Module"]
        uart = _PIN_MAPS["Arduino"]["uart"]
        assert alloc["TX"] == uart["tx"]
        assert alloc["RX"] == uart["rx"]

    def test_bluetooth_hc05_esp32_gets_uart_pins(self):
        """Bluetooth_HC05 在 ESP32 上應分配 UART tx/rx。"""
        result = allocate_pins("ESP32", ["Bluetooth_HC05"], use_uart=True)
        alloc = result["allocation"]["Bluetooth_HC05"]
        uart = _PIN_MAPS["ESP32"]["uart"]
        assert alloc["TX"] == uart["tx"]
        assert alloc["RX"] == uart["rx"]

    def test_uart_allocation_returns_labels(self):
        """UART 元件要有 pin_labels 回傳。"""
        result = allocate_pins("Arduino", ["GPS_Module"], use_uart=True)
        label = result["pin_labels"].get("GPS_Module", "")
        assert "TX=" in label
        assert "RX=" in label


# ── 各 MCU 基本分配 ───────────────────────────────────────────

class TestPerMCUAllocation:
    """GA-C2：確保每款 MCU 都能正確用 allocate_pins 分配。"""

    def test_arduino_digital_allocation(self):
        result = allocate_pins("Arduino", ["Button"])
        assert "Button" in result["allocation"]
        pin = result["allocation"]["Button"]["SIG"]
        assert pin in _PIN_MAPS["Arduino"]["digital"] + _PIN_MAPS["Arduino"]["pwm"]

    def test_esp32_analog_allocation(self):
        result = allocate_pins("ESP32", ["SoilMoisture"])
        pin = result["allocation"]["SoilMoisture"]["AO"]
        assert pin in _PIN_MAPS["ESP32"]["analog"]

    def test_rpi_pwm_allocation(self):
        result = allocate_pins("RPi", ["Servo"])
        pin = result["allocation"]["Servo"]["SIG"]
        # RPi PWM 是硬體 PWM，確保在 pwm 或 digital pool 內
        valid = _PIN_MAPS["RPi"]["pwm"] + _PIN_MAPS["RPi"]["digital"]
        assert pin in valid

    def test_microbit_analog_allocation(self):
        result = allocate_pins("Microbit", ["SoilMoisture"])
        pin = result["allocation"]["SoilMoisture"]["AO"]
        assert pin in _PIN_MAPS["Microbit"]["analog"]


# ── 衝突檢測 ──────────────────────────────────────────────────

class TestConflictDetection:
    """GA-C2：同一 MCU 多個元件不得共用 pin。"""

    def test_no_pin_collision_across_mcus(self):
        """Arduino 同時接多個 digital 元件，pin 不重複。"""
        result = allocate_pins("Arduino", ["Button", "Relay", "PIR"])
        alloc = result["allocation"]
        non_i2c_pins = [
            str(pin)
            for comp_pins in alloc.values()
            for pin in comp_pins.values()
        ]
        assert len(non_i2c_pins) == len(set(non_i2c_pins)), \
            f"Pin collision: {non_i2c_pins}"

    def test_esp32_output_not_on_input_only(self):
        """ESP32 輸出元件 pin 不可落在 input-only GPIO 34/35/36/39。"""
        result = allocate_pins("ESP32", ["NeoPixel", "Relay"])
        input_only = {34, 35, 36, 39}
        for comp, pins in result["allocation"].items():
            for tag, pin in pins.items():
                if isinstance(pin, int):
                    assert pin not in input_only, \
                        f"ESP32 {comp}.{tag}={pin} on input-only GPIO"


# ── SWL3：被動元件（電阻/電容） ───────────────────────────────

class TestPassives:
    """SWL3：resolve_wiring/to_json 輸出結構化被動元件供 schematic 畫節點。"""

    def _pin(self, wiring, comp, comp_pin):
        return next(p for p in wiring[comp]["pins"] if p["comp"] == comp_pin)

    def test_led_series_resistor(self):
        """LED 訊號腳帶串聯 220Ω 電阻。"""
        w = resolve_wiring("Arduino", ["LED_Single"])
        passive = self._pin(w, "LED_Single", "+")["passive"]
        assert passive == {"kind": "R", "value": "220Ω", "topo": "series"}

    def test_dht22_pullup_resistor(self):
        """DHT22 DATA 腳帶 4.7kΩ 上拉電阻。"""
        w = resolve_wiring("Arduino", ["TempHumid"])
        passive = self._pin(w, "TempHumid", "DATA")["passive"]
        assert passive == {"kind": "R", "value": "4.7kΩ", "topo": "pullup"}

    def test_ldr_divider_resistor(self):
        """LDR 帶 10kΩ 分壓電阻。"""
        w = resolve_wiring("Arduino", ["Light"])
        passive = self._pin(w, "Light", "LDR")["passive"]
        assert passive["topo"] == "divider" and passive["value"] == "10kΩ"

    def test_non_passive_pin_is_none(self):
        """無被動元件的訊號腳 passive=None（PIR OUT 直連）。"""
        w = resolve_wiring("Arduino", ["PIR"])
        assert self._pin(w, "PIR", "OUT")["passive"] is None

    def test_ic_module_has_decoupling(self):
        """IC 模組（OLED）帶 100nF 去耦電容。"""
        w = resolve_wiring("Arduino", ["OLED"])
        decoup = w["OLED"]["decoupling"]
        assert decoup == [{"kind": "C", "value": "100nF", "topo": "decoupling"}]

    def test_bare_component_no_decoupling(self):
        """裸件（LED/Button）不帶去耦電容。"""
        w = resolve_wiring("Arduino", ["LED_Single", "Button"])
        assert "decoupling" not in w["LED_Single"]
        assert "decoupling" not in w["Button"]

    def test_to_json_power_passives(self):
        """to_json 帶 MCU 電源軌 bulk + 去耦電容。"""
        j = to_json("Arduino", ["LED_Single"])
        pp = j["power_passives"]
        topos = {p["topo"] for p in pp}
        assert "bulk" in topos and "decoupling" in topos
        assert all(p["kind"] == "C" for p in pp)
