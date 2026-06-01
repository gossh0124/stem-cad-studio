"""
microbit.py — micro:bit firmware code generation.
"""
from __future__ import annotations
from datetime import date

from ..wiring import allocate_pins, PinAllocationError
from .templates import stem_header_lines


def _gen_microbit(outputs: list[str], sensors: list[str], power: str,
                  project_name: str = "", plan: str = "") -> str:

    today = date.today().strftime("%Y/%m/%d")
    all_comps = outputs + sensors
    result = allocate_pins("Microbit", all_comps)
    alloc = result["allocation"]

    def p(comp: str, tag: str) -> object:
        if comp not in alloc:
            raise PinAllocationError(f"元件 {comp} 未分配（allocate_pins 結果中無此元件）")
        m = alloc[comp]
        if tag not in m:
            raise PinAllocationError(f"{comp}.{tag} 未分配（COMP_PIN_NEEDS 與 allocation 不符）")
        v = m[tag]
        return str(v).lstrip("P") if isinstance(v, str) and v.startswith("P") else v

    lines = [
        "# ═══════════════════════════════════════════════════",
        f"# CADHLLM 自動合成韌體 — {today}",
        f"# Brain: micro:bit  Power: {power}",
        f"# Outputs: {', '.join(outputs) or '(無)'}",
        f"# Sensors: {', '.join(sensors) or '(無)'}",
        "# IDE: Mu Editor / MakeCode Python",
        "# ═══════════════════════════════════════════════════",
        "",
        *stem_header_lines(outputs, sensors, project_name, plan, "#"),
        "from microbit import *",
    ]
    if "Ultrasonic" in sensors:
        lines.append("import machine")
        lines.append("import utime")
    if "TempHumid" in sensors:
        lines.append("from microbit import i2c")
    if "OLED" in outputs:
        lines.append("from ssd1306 import SSD1306_I2C  # 需上傳 ssd1306.py 至 micro:bit")
    if "LCD" in outputs:
        lines.append("from i2c_lcd import I2cLcd  # 需上傳 i2c_lcd.py 至 micro:bit")
    if any(o.startswith("Buzzer") for o in outputs) or "Speaker" in outputs:
        lines.append("import music")
    if "Servo" in outputs:
        lines.append("import machine as _m")

    lines.extend(["", "# ── 初始化 ──"])
    if "OLED" in outputs:
        lines.append("oled = SSD1306_I2C(128, 64, i2c)")
    if "LCD" in outputs:
        lines.append("lcd = I2cLcd(i2c, 0x27, 2, 16)")
    if "Servo" in outputs:
        lines.append(f"servo_pin = _m.Pin(_m.Pin.board.P{p('Servo', 'SIG')}, _m.Pin.OUT)")
    if "NeoPixel" in outputs:
        lines.append("import neopixel")
        lines.append(f"np = neopixel.NeoPixel(pin{p('NeoPixel', 'DIN')}, 8)")

    lines.extend(["", 'display.scroll("CADHLLM")', "", "while True:"])

    has_sensor_logic = False
    if "TempHumid" in sensors:
        lines.append("    temp = temperature()  # 內建溫度感測器")
        has_sensor_logic = True
    if "Light" in sensors:
        lines.append("    light_val = display.read_light_level()  # 0-255")
        has_sensor_logic = True
    if "SoilMoisture" in sensors:
        lines.append(f"    soil_val = pin{p('SoilMoisture', 'AO')}.read_analog()  # 0-1023")
        has_sensor_logic = True
    if "Ultrasonic" in sensors:
        trig = p("Ultrasonic", "TRIG")
        echo = p("Ultrasonic", "ECHO")
        lines.append(f"    pin{trig}.write_digital(0); utime.sleep_us(2)")
        lines.append(f"    pin{trig}.write_digital(1); utime.sleep_us(10)")
        lines.append(f"    pin{trig}.write_digital(0)")
        lines.append(f"    t = machine.time_pulse_us(pin{echo}, 1, 30000)")
        lines.append("    dist_cm = t / 58.0 if t > 0 else 999")
        has_sensor_logic = True
    if "PIR" in sensors:
        lines.append(f"    motion = pin{p('PIR', 'OUT')}.read_digital()")
        has_sensor_logic = True
    if "IR" in sensors:
        lines.append(f"    ir_val = pin{p('IR', 'OUT')}.read_digital()")
        has_sensor_logic = True

    if has_sensor_logic:
        lines.append("")

    has_ext_display = "OLED" in outputs or "LCD" in outputs
    if has_ext_display:
        disp_lines = []
        if "OLED" in outputs:
            disp_lines.append("    oled.fill(0)")
            if "TempHumid" in sensors:
                disp_lines.append('    oled.text("Temp:" + str(temp) + "C", 0, 0)')
            if "Light" in sensors:
                disp_lines.append('    oled.text("Light:" + str(light_val), 0, 16)')
            if "Ultrasonic" in sensors:
                disp_lines.append('    oled.text("Dist:" + str(int(dist_cm)), 0, 32)')
            if "SoilMoisture" in sensors:
                disp_lines.append('    oled.text("Soil:" + str(soil_val), 0, 48)')
            if not sensors:
                disp_lines.append('    oled.text("CADHLLM", 30, 28)')
            disp_lines.append("    oled.show()")
        elif "LCD" in outputs:
            disp_lines.append("    lcd.clear()")
            if "TempHumid" in sensors:
                disp_lines.append('    lcd.putstr("Temp:" + str(temp) + "C")')
            elif "Ultrasonic" in sensors:
                disp_lines.append('    lcd.putstr("D:" + str(int(dist_cm)) + "cm")')
            elif "SoilMoisture" in sensors:
                disp_lines.append('    lcd.putstr("Soil:" + str(soil_val))')
            else:
                disp_lines.append('    lcd.putstr("CADHLLM Ready")')
        lines.extend(disp_lines)
        lines.append("")

    handled_outputs: set[str] = set()
    _has_buzz = [o for o in outputs if o.startswith("Buzzer")]
    if "PIR" in sensors and _has_buzz:
        lines.append("    if motion:")
        lines.append("        music.pitch(1000, 200)")
        handled_outputs.update(_has_buzz)
    elif "PIR" in sensors and "NeoPixel" in outputs:
        lines.append("    if motion:")
        lines.append("        for i in range(8): np[i] = (255, 0, 0)")
        lines.append("        np.show()")
        lines.append("    else:")
        lines.append("        for i in range(8): np[i] = (0, 0, 0)")
        lines.append("        np.show()")
        handled_outputs.add("NeoPixel")
    elif "Ultrasonic" in sensors and _has_buzz:
        lines.append("    if dist_cm < 20:")
        lines.append("        music.pitch(2000, 100)")
        handled_outputs.update(_has_buzz)
    elif "Ultrasonic" in sensors and "Servo" in outputs:
        lines.append("    angle = max(0, min(180, int(dist_cm * 1.8)))")
        lines.append(f"    pin{p('Servo', 'SIG')}.write_analog(int(angle / 180 * 1023))")
        handled_outputs.add("Servo")
    elif "SoilMoisture" in sensors and "Relay" in outputs:
        out_pin = p("Relay", "IN")
        lines.append("    if soil_val > 600:  # 太乾")
        lines.append(f"        pin{out_pin}.write_digital(1)")
        lines.append("    else:")
        lines.append(f"        pin{out_pin}.write_digital(0)")
        handled_outputs.add("Relay")
    elif "Light" in sensors and not has_ext_display:
        lines.append("    if light_val < 80:")
        lines.append("        display.show(Image.HEART)")
        lines.append("    else:")
        lines.append("        display.show(Image.HAPPY)")
    elif "TempHumid" in sensors and not has_ext_display:
        lines.append('    display.scroll(str(temp) + "C")')
    elif "SoilMoisture" in sensors and not has_ext_display:
        lines.append("    if soil_val > 600:")
        lines.append("        display.show(Image.SAD)")
        lines.append("    else:")
        lines.append("        display.show(Image.HAPPY)")
    elif not has_ext_display:
        lines.append("    if button_a.is_pressed():")
        lines.append("        display.show(Image.YES)")
        lines.append("    elif button_b.is_pressed():")
        lines.append("        display.show(Image.NO)")
        lines.append("    else:")
        lines.append("        display.show(Image.HEART)")

    if _has_buzz and not (set(_has_buzz) & handled_outputs):
        lines.append("    if button_a.is_pressed():")
        lines.append("        music.pitch(440, 200)")
    if "Servo" in outputs and "Servo" not in handled_outputs:
        lines.append("    if button_a.is_pressed():")
        lines.append(f"        pin{p('Servo', 'SIG')}.write_analog(26)   # 0 deg")
        lines.append("    elif button_b.is_pressed():")
        lines.append(f"        pin{p('Servo', 'SIG')}.write_analog(128)  # 180 deg")
    if "NeoPixel" in outputs and "NeoPixel" not in handled_outputs:
        lines.append("    if button_a.is_pressed():")
        lines.append("        for i in range(8): np[i] = (0, 255, 0)")
        lines.append("        np.show()")

    lines.append("    sleep(200)")
    return "\n".join(lines)
