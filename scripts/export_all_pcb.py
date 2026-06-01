"""scripts/export_all_pcb.py — 批次匯出所有元件 PCB GLB/STL 模型。

用法：.venv\\Scripts\\python.exe scripts\\export_all_pcb.py
"""
from __future__ import annotations

import sys
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.cad.pcb_common import export_pcb  # noqa: E402
from lib.cad.pcb_body import build_arduino_pcb_body  # noqa: E402
from lib.cad.pcb_boards import (  # noqa: E402
    build_esp32_pcb_body,
    build_rpi_pcb_body,
    build_microbit_pcb_body,
)
from lib.cad.pcb_sensors import (  # noqa: E402
    build_temp_humid_pcb_body,
    build_ultrasonic_pcb_body,
    build_pir_pcb_body,
    build_soil_moisture_pcb_body,
    build_light_sensor_pcb_body,
    build_ir_sensor_pcb_body,
)
from lib.cad.pcb_peripherals import (  # noqa: E402
    build_relay_pcb_body,
    build_oled_pcb_body,
    build_lcd_pcb_body,
    build_eink_pcb_body,
    build_led_matrix_pcb_body,
    build_mp3_pcb_body,
    build_joystick_pcb_body,
    build_chassis_pcb_body,
)

BUILDERS: list[tuple[str, callable]] = [
    ("Arduino-Uno-class",        build_arduino_pcb_body),
    ("ESP32-class",              build_esp32_pcb_body),
    ("RaspberryPi-class",        build_rpi_pcb_body),
    ("Microbit-class",           build_microbit_pcb_body),
    ("Sensor-TempHumid-class",   build_temp_humid_pcb_body),
    ("Sensor-Ultrasonic-class",  build_ultrasonic_pcb_body),
    ("Sensor-PIR-class",         build_pir_pcb_body),
    ("Sensor-SoilMoisture-class", build_soil_moisture_pcb_body),
    ("Sensor-Light-class",       build_light_sensor_pcb_body),
    ("Sensor-IR-class",          build_ir_sensor_pcb_body),
    ("Relay-Module-class",       build_relay_pcb_body),
    ("Display-OLED-class",       build_oled_pcb_body),
    ("Display-LCD-class",        build_lcd_pcb_body),
    ("Display-EInk-class",       build_eink_pcb_body),
    ("LED-Matrix-class",         build_led_matrix_pcb_body),
    ("MP3-Module-class",         build_mp3_pcb_body),
    ("Joystick-class",           build_joystick_pcb_body),
    ("Chassis-Car-class",        build_chassis_pcb_body),
]


def main() -> int:
    shells_dir = ROOT / "shells"
    ok = 0
    fail = 0
    t0 = time.time()

    print(f"=== PCB Body 批次匯出 ({len(BUILDERS)} 元件) ===\n")
    for cls_name, builder in BUILDERS:
        try:
            t1 = time.time()
            compound = builder()
            out_dir = str(shells_dir / cls_name)
            export_pcb(compound, out_dir, cls_name)
            bb = compound.bounding_box()
            dt = time.time() - t1
            print(f"  {cls_name:<28} "
                  f"{bb.max.X-bb.min.X:>6.1f}×{bb.max.Y-bb.min.Y:>5.1f}"
                  f"×{bb.max.Z-bb.min.Z:>5.1f}mm  ({dt:.1f}s)")
            ok += 1
        except Exception as exc:
            print(f"  ✗ {cls_name}: {exc}")
            fail += 1

    elapsed = time.time() - t0
    print(f"\n=== 完成：{ok} 成功，{fail} 失敗，共 {elapsed:.1f}s ===")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
