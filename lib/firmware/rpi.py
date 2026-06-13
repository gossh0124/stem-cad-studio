"""
rpi.py — Raspberry Pi firmware code generation.
"""
from __future__ import annotations
from datetime import date

from ..wiring import allocate_pins, PinAllocationError
from .templates import match_reactions, stem_header_lines


def _gen_rpi(outputs: list[str], sensors: list[str], power: str,
             project_name: str = "", plan: str = "") -> str:

    today = date.today().strftime("%Y/%m/%d")
    all_comps = outputs + sensors
    result = allocate_pins("RPi", all_comps)
    alloc = result["allocation"]

    def p(comp: str, tag: str) -> object:
        """從 allocate_pins 回傳值取 pin 號碼。

        Phase 0 接線硬化：comp 或 tag 缺失時 raise PinAllocationError，
        不再靜默回 '?'。
        """
        if comp not in alloc:
            raise PinAllocationError(
                f"Component '{comp}' not found in pin allocation. "
                f"Available components: {list(alloc.keys())}"
            )
        comp_alloc = alloc[comp]
        if tag not in comp_alloc:
            raise PinAllocationError(
                f"Tag '{tag}' not found for component '{comp}'. "
                f"Available tags: {list(comp_alloc.keys())}"
            )
        return comp_alloc[tag]

    lines = [
        "# ═══════════════════════════════════════════════════",
        f"# CADHLLM 自動合成韌體 — {today}",
        f"# Brain: Raspberry Pi  Power: {power}",
        f"# Outputs: {', '.join(outputs) or '(無)'}",
        f"# Sensors: {', '.join(sensors) or '(無)'}",
        "# IDE: Thonny / VS Code  執行: python3 main.py",
        "# ═══════════════════════════════════════════════════",
        "",
        *stem_header_lines(outputs, sensors, project_name, plan, "#"),
        "from gpiozero import LED, PWMLED, Buzzer, OutputDevice",
        "from time import sleep, time",
        "import signal, sys",
        "",
    ]
    if "TempHumid" in sensors:
        lines.append("import Adafruit_DHT  # pip install Adafruit_DHT")
    if "Ultrasonic" in sensors:
        lines.append("from gpiozero import DistanceSensor")
    lines.append("")

    if "LED_Single" in outputs:
        lines.append(f"led = LED({p('LED_Single', '+')})")
    if "LED_RGB" in outputs:
        lines.append(f"led_r = PWMLED({p('LED_RGB', 'R')})")
        lines.append(f"led_g = PWMLED({p('LED_RGB', 'G')})")
        lines.append(f"led_b = PWMLED({p('LED_RGB', 'B')})")
    if any(o.startswith("Buzzer") for o in outputs):
        buzz_comp = next(o for o in outputs if o.startswith("Buzzer"))
        lines.append(f"buzzer = Buzzer({p(buzz_comp, 'SIG')})")
    if "Relay" in outputs:
        lines.append(f"relay = OutputDevice({p('Relay', 'IN')}, active_high=False)")
    if "TempHumid" in sensors:
        lines.append(f"DHT_PIN = {p('TempHumid', 'DATA')}")
    if "Ultrasonic" in sensors:
        lines.append(f"sonar = DistanceSensor(echo={p('Ultrasonic', 'ECHO')}, trigger={p('Ultrasonic', 'TRIG')})")
    if "SoilMoisture" in sensors:
        lines.append("from gpiozero import MCP3008")
        lines.append("soil_sensor = MCP3008(channel=0)  # 需 MCP3008 ADC")
    if "PIR" in sensors:
        lines.append("from gpiozero import MotionSensor")
        lines.append(f"pir = MotionSensor({p('PIR', 'OUT')})")
    if "Light" in sensors:
        lines.append("from gpiozero import LightSensor")
        lines.append(f"light_sensor = LightSensor({p('Light', 'LDR')})")

    lines.extend([
        "",
        "def cleanup(sig, frame):",
        "    sys.exit(0)",
        "signal.signal(signal.SIGINT, cleanup)",
        "",
        'print("CADHLLM RPi Ready")',
        "while True:",
    ])

    if "TempHumid" in sensors:
        lines.append("    h, t = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, DHT_PIN)")
    if "Ultrasonic" in sensors:
        lines.append("    dist_cm = sonar.distance * 100")
    if "SoilMoisture" in sensors:
        lines.append("    soil_pct = round((1023 - soil_sensor.value * 1023) / 1023 * 100)")
    if "PIR" in sensors:
        lines.append("    motion = pir.is_active")
    if "Light" in sensors:
        lines.append("    light_pct = round((1 - light_sensor.value) * 100)")
    lines.append("")

    reactions, handled = match_reactions(sensors, outputs)
    _rpi_action_map = {
        "LED_Single":  {"on": "led.on()", "off": "led.off()"},
        "Buzzer_Active":  {"on": "buzzer.on()", "off": "buzzer.off()"},
        "Buzzer_Passive": {"on": "buzzer.on()", "off": "buzzer.off()"},
        "Relay":       {"on": "relay.on()", "off": "relay.off()"},
    }
    _rpi_cond_map = {
        "soilPct < 40":  "soil_pct < 40",
        "motion == 1":   "motion",
        "dist_cm < 20":  "dist_cm < 20",
        "dist_cm < 30":  "dist_cm < 30",
        "lightPct < 30": "light_pct < 30",
        "temp > 35.0":   "t > 35.0",
        "temp > 30.0":   "t > 30.0",
    }
    if reactions:
        lines.append("    # ── 感測→致動規則 ──")
        for r in reactions:
            py_cond = _rpi_cond_map.get(r["condition"], r["condition"])
            acts = _rpi_action_map.get(r["output"])
            if not acts:
                # 該 reaction output 在 RPi 沒有真正的 gpiozero 致動實作,
                # 不能靜默產生「只有註解、什麼都不做」的 if/else no-op,
                # 那會產出看似實作卻完全失效的韌體。改為明確 raise。
                raise NotImplementedError(
                    f"RPi reaction output '{r['output']}' has no gpiozero "
                    f"actuation mapping in _rpi_action_map. Supported outputs: "
                    f"{sorted(_rpi_action_map.keys())}. Extend _rpi_action_map "
                    f"(and the device-init block) before pairing this output, "
                    f"or exclude it from REACTION_RULES."
                )
            on_act = acts["on"]
            off_act = acts["off"]
            lines.append(f"    # {r['label']}")
            lines.append(f"    if {py_cond}:")
            lines.append(f"        {on_act}")
            lines.append(f"    else:")
            lines.append(f"        {off_act}")
        lines.append("")

    for o in outputs:
        if o in handled:
            continue
        if o == "LED_Single":
            lines.append("    led.toggle()")
        elif o == "LED_RGB":
            lines.append("    led_r.value = 0; led_g.value = 0.6; led_b.value = 1.0")

    serial_parts: list[str] = []
    if "TempHumid" in sensors:
        serial_parts.append('f"T:{t:.1f}C H:{h:.0f}%"')
    if "SoilMoisture" in sensors:
        serial_parts.append('f"Soil:{soil_pct}%"')
    if "Ultrasonic" in sensors:
        serial_parts.append('f"Dist:{dist_cm:.1f}cm"')
    if "Light" in sensors:
        serial_parts.append('f"Light:{light_pct}%"')
    if "PIR" in sensors:
        serial_parts.append('f"PIR:{motion}"')
    if serial_parts:
        lines.append(f'    print({" + \"  \" + ".join(serial_parts)})')

    lines.append("    sleep(0.1)")
    return "\n".join(lines)
