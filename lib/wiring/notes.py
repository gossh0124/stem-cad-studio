"""
wiring_notes.py — Educational wiring explanation generator (Phase III)

Generates a dict of wire_id -> educational description string,
designed for embedding as SVG <title> tooltips or side-panel notes.
"""
from __future__ import annotations

from .engine import COMP_PIN_NEEDS, WIRING_TEMPLATES, _I2C_HW_PINS


# ── Pin role classification ────────────────────────────────────
_PWM_CONTROLLED = {"LED_RGB", "Buzzer_Passive", "Servo", "DCMotor"}
_PWM_ASPECT = {
    "LED_RGB": "亮度",
    "Buzzer_Passive": "音調",
    "Servo": "轉角",
    "DCMotor": "轉速",
}


def _classify_pin_role(comp: str, pin_need) -> str:
    """Classify a pin need into an educational category."""
    if pin_need.type == "i2c":
        return "i2c"
    if pin_need.type == "analog":
        return "analog"
    if pin_need.type == "pwm" and comp in _PWM_CONTROLLED:
        return "pwm"
    return "digital"


def _make_digital_note(comp_label: str, mcu_pin: str) -> str:
    return f"{comp_label} 使用數位腳位 {mcu_pin}，以 HIGH/LOW 訊號控制開關"


def _make_pwm_note(comp_label: str, mcu_pin: str, comp_key: str) -> str:
    aspect = _PWM_ASPECT.get(comp_key, "輸出")
    return f"{comp_label} 使用 PWM 腳位 {mcu_pin}，透過脈寬調變控制{aspect}"


def _make_i2c_note(comp_label: str, brain: str, addr: str = "0x3C") -> str:
    i2c_pins = _I2C_HW_PINS.get(brain, ("A4", "A5"))
    sda, scl = i2c_pins
    return (
        f"{comp_label} 透過 I2C 匯流排（SDA:{sda}, SCL:{scl}）"
        f"與 MCU 通訊，地址為 {addr}"
    )


def _make_analog_note(comp_label: str, mcu_pin: str) -> str:
    return f"{comp_label} 輸出類比訊號到 {mcu_pin}，MCU 透過 ADC 讀取 0-1023 數值"


def _make_power_note(comp_label: str, vcc: str) -> str:
    return f"{comp_label} 供電：VCC={vcc}, GND 共地"


# ── I2C address lookup ─────────────────────────────────────────
_I2C_ADDRS = {
    "OLED": "0x3C",
    "LCD": "0x27",
}


def generate_wiring_notes(
    wiring_result: dict,
    components: list[str],
    brain: str = "Arduino",
) -> dict:
    """
    Generate educational descriptions for each wire connection.

    Args:
        wiring_result: output of resolve_wiring() — {comp: {label, pins}}
        components: list of component short names
        brain: MCU key (for I2C pin info)

    Returns:
        dict of wire_id -> educational description string
        e.g. {"MCU_D2_to_PIR_OUT": "HC-SR501 PIR ... HIGH/LOW ..."}
    """
    notes: dict[str, str] = {}

    for comp_key in components:
        spec = wiring_result.get(comp_key)
        if not spec:
            continue

        label = spec["label"]
        tmpl = WIRING_TEMPLATES.get(comp_key)
        vcc = tmpl.vcc if tmpl else None

        # Power note
        if vcc:
            power_wire_id = f"MCU_{vcc}_to_{comp_key}_VCC"
            notes[power_wire_id] = _make_power_note(label, vcc)

        # Data pins
        pin_needs = COMP_PIN_NEEDS.get(comp_key, [])
        for pin_info in spec["pins"]:
            mcu_pin = pin_info["mcu"]
            comp_pin = pin_info["comp"]

            # Skip non-data pins
            if mcu_pin in ("GND", "5V", "3.3V", "EXT", "SPK", "SPK-", "LOAD"):
                continue
            if comp_pin in ("VCC", "GND"):
                continue

            wire_id = f"MCU_{mcu_pin}_to_{comp_key}_{comp_pin}"

            # Find matching pin need for classification
            matched_need = None
            for pn in pin_needs:
                if pn.tag == comp_pin:
                    matched_need = pn
                    break

            if matched_need is None:
                notes[wire_id] = f"{label} 連接到 {mcu_pin}"
                continue

            role = _classify_pin_role(comp_key, matched_need)

            if role == "i2c":
                addr = _I2C_ADDRS.get(comp_key, "0x3C")
                notes[wire_id] = _make_i2c_note(label, brain, addr)
            elif role == "pwm":
                notes[wire_id] = _make_pwm_note(label, mcu_pin, comp_key)
            elif role == "analog":
                notes[wire_id] = _make_analog_note(label, mcu_pin)
            else:
                notes[wire_id] = _make_digital_note(label, mcu_pin)

    return notes
