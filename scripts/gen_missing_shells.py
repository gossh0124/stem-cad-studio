"""Generate parametric 3D shell STL files for component types that are missing.

Uses build123d to create recognizable shapes for STEM components.
Run: .venv/Scripts/python.exe scripts/gen_missing_shells.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHELLS = REPO / "shells"

try:
    from build123d import (
        BuildPart, Box, Cylinder, Sphere,
        Locations, Align, Mode,
        export_stl,
    )
except ImportError as exc:
    sys.exit(f"build123d import failed: {exc}")


def _stl_triangle_count(stl_path: Path) -> int:
    """Read the real triangle count from an STL file.

    Binary STL: 80-byte header followed by a uint32 (little-endian) triangle
    count at byte offset 80. ASCII STL: count "facet normal" occurrences.
    Avoids the old file-size//50 heuristic which mis-counted the 84-byte
    header and was entirely wrong for ASCII output.
    """
    with open(stl_path, "rb") as fh:
        head = fh.read(84)
        # ASCII STL files start with the literal token "solid" and have no
        # valid uint32 count; detect and fall back to facet counting.
        if head[:5].lower() == b"solid" and b"facet" in head:
            text = stl_path.read_text(encoding="ascii", errors="replace")
            return text.count("facet normal")
        if len(head) < 84:
            raise ValueError(f"STL too short to contain a header+count: {stl_path}")
        return struct.unpack("<I", head[80:84])[0]


def _save(name: str, part, label: str, kind: str = "pcb_body"):
    d = SHELLS / name
    d.mkdir(parents=True, exist_ok=True)
    stl_path = d / "pcb_body.stl"
    export_stl(part, str(stl_path))
    tris = _stl_triangle_count(stl_path)
    meta = {"class_name": name, "kind": kind, "label": label, "tris": tris,
            "files": {"pcb_body_stl": "pcb_body.stl"}}
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  [OK] {name:30s} -> {stl_path.stat().st_size:>8,} bytes  ({tris} tris)")


# NOTE: gen_battery_aa removed 2026-06-06 — it produced a single-colour Box+2-holes
# placeholder (user feedback: 同色長方體+頂面兩洞). Battery-AA is now baked as a
# multi-colour body by lib/cad/component_bodies.gen_battery_aa (via export_pcb).


def gen_battery_lipo():
    """LiPo battery: flat padded rectangle with rounded top edges."""
    with BuildPart() as p:
        Box(50, 30, 8)
        with Locations([(25, 0, 0)]):
            Box(4, 8, 6, mode=Mode.ADD)  # connector tab
    _save("Battery-LiPo-class", p.part, "LiPo Battery")


def gen_button():
    """Tactile push button: square body + round cap."""
    with BuildPart() as p:
        Box(12, 12, 4.3)
        with Locations([(0, 0, 4.3 / 2)]):
            Cylinder(3.5, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))
        for dx, dy in [(-5.5, -5.5), (5.5, -5.5), (-5.5, 5.5), (5.5, 5.5)]:
            with Locations([(dx, dy, -4.3 / 2)]):
                Cylinder(0.5, 3, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.ADD)
    _save("Button-class", p.part, "Tactile Button")


def gen_buzzer_active():
    """Active buzzer: cylinder with small feet."""
    with BuildPart() as p:
        Cylinder(6, 9.5)
        with Locations([(0, 0, 9.5 / 2)]):
            Cylinder(5, 0.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        for dx in [-2.54 / 2, 2.54 / 2]:
            with Locations([(dx, 0, -9.5 / 2)]):
                Cylinder(0.3, 4, align=(Align.CENTER, Align.CENTER, Align.MAX))
    _save("Buzzer-Active-class", p.part, "Active Buzzer")


def gen_buzzer_passive():
    """Passive buzzer: cylinder, slightly shorter than active, with top hole."""
    with BuildPart() as p:
        Cylinder(6, 8.5)
        with Locations([(0, 0, 8.5 / 2)]):
            Cylinder(2, 1, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        for dx in [-2.54 / 2, 2.54 / 2]:
            with Locations([(dx, 0, -8.5 / 2)]):
                Cylinder(0.3, 4, align=(Align.CENTER, Align.CENTER, Align.MAX))
    _save("Buzzer-Passive-class", p.part, "Passive Buzzer")


def gen_led_pwm():
    """Single 5mm LED: dome on cylindrical body with 2 leg pins."""
    with BuildPart() as p:
        Cylinder(2.5, 6)
        with Locations([(0, 0, 6 / 2)]):
            Sphere(2.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations([(0, 0, 6 / 2)]):
            Cylinder(2.85, 1, align=(Align.CENTER, Align.CENTER, Align.MAX))
        for dx in [-1.27, 1.27]:
            with Locations([(dx, 0, -6 / 2)]):
                Cylinder(0.25, 12, align=(Align.CENTER, Align.CENTER, Align.MAX))
    _save("Lighting-LED-PWM-class", p.part, "Single LED")


def gen_led_rgb():
    """RGB 5mm LED: slightly wider dome, 4 leg pins."""
    with BuildPart() as p:
        Cylinder(2.5, 6)
        with Locations([(0, 0, 6 / 2)]):
            Sphere(2.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations([(0, 0, 6 / 2)]):
            Cylinder(2.85, 1, align=(Align.CENTER, Align.CENTER, Align.MAX))
        for dx in [-1.905, -0.635, 0.635, 1.905]:
            with Locations([(dx, 0, -6 / 2)]):
                Cylinder(0.25, 12, align=(Align.CENTER, Align.CENTER, Align.MAX))
    _save("Lighting-LED-RGB-class", p.part, "RGB LED")


def gen_neopixel():
    """NeoPixel LED strip: long PCB with raised LED pads."""
    with BuildPart() as p:
        Box(100, 12, 2)  # PCB strip
        for i in range(8):
            x = -100 / 2 + 6.25 + i * 12.5
            with Locations([(x, 0, 2 / 2)]):
                Box(5, 5, 1.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
    _save("Lighting-NeoPixel-class", p.part, "NeoPixel Strip")


def gen_potentiometer():
    """Rotary potentiometer: body + shaft + 3 pins."""
    with BuildPart() as p:
        Cylinder(8.5, 7)
        with Locations([(0, 0, 7 / 2)]):
            Cylinder(3, 8, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # D-shaft flat
        with Locations([(3.5, 0, 7 / 2 + 4)]):
            Box(2, 6, 8, mode=Mode.SUBTRACT)
        for dx in [-5.08, 0, 5.08]:
            with Locations([(dx, 0, -7 / 2)]):
                Cylinder(0.4, 5, align=(Align.CENTER, Align.CENTER, Align.MAX))
    _save("Potentiometer-class", p.part, "Potentiometer")


def gen_remote():
    """NRF24L01 module: small PCB with 2x4 header + antenna trace."""
    with BuildPart() as p:
        Box(30, 16, 2)  # PCB
        with Locations([(-30 / 2 + 4, 0, -2 / 2)]):
            Box(8, 10, 8.5, align=(Align.CENTER, Align.CENTER, Align.MAX))  # 2x4 pin header
        with Locations([(30 / 2 - 3, 0, 2 / 2)]):
            Cylinder(1, 12, align=(Align.CENTER, Align.CENTER, Align.MIN))  # antenna
    _save("Remote-class", p.part, "NRF24 Module")


def gen_switch():
    """Toggle switch: rectangular body with toggle lever."""
    with BuildPart() as p:
        Box(14, 8, 8)
        with Locations([(0, 0, 8 / 2)]):
            Cylinder(2, 5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        for dx in [-4.7, 0, 4.7]:
            with Locations([(dx, 0, -8 / 2)]):
                Cylinder(0.5, 4, align=(Align.CENTER, Align.CENTER, Align.MAX))
    _save("Switch-class", p.part, "Toggle Switch")


def gen_usb_5v():
    """USB 5V adapter: rectangular block with USB-A port cutout."""
    with BuildPart() as p:
        Box(40, 20, 11)
        # USB-A port recess
        with Locations([(-40 / 2, 0, 1)]):
            Box(8, 13, 5.5, align=(Align.MIN, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)
        # barrel jack on other side
        with Locations([(40 / 2 - 2, 0, -11 / 2)]):
            Cylinder(5.5 / 2, 10, align=(Align.CENTER, Align.CENTER, Align.MAX))
    _save("USB-5V-class", p.part, "USB 5V Adapter")


def gen_ac_adapter():
    """AC adapter: rectangular block with barrel plug."""
    with BuildPart() as p:
        Box(50, 25, 15)
        # barrel connector
        with Locations([(50 / 2, 0, 0)]):
            Cylinder(5.5 / 2, 10, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    _save("AC-Adapter-class", p.part, "AC Adapter")


# NOTE 2026-06-06: the single-colour Button/Buzzer/LED/NeoPixel/Potentiometer/Switch/
# USB-5V/AC-Adapter/Remote generators are SUPERSEDED by multi-colour, datasheet-accurate
# builders in lib/cad/component_bodies_fidelity.py (Remote was also the WRONG part — NRF24
# vs the SSOT IR receiver). They stay defined for reference but are no longer baked here.
# NOTE 2026-06-07: gen_battery_lipo is ALSO superseded — Battery-LiPo-class is now baked
# as a multi-colour foil-pouch + JST body by lib/cad/component_bodies_fidelity.gen_battery_lipo
# (via export_pcb). The single-colour Box+tab placeholder here is retired from the bake.
_GENERATORS: list = []


def main():
    print(f"Generating {len(_GENERATORS)} missing component shells ...\n")
    ok, fail = 0, 0
    for fn in _GENERATORS:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {fn.__name__}: {e}")
            fail += 1
    print(f"\nDone: {ok} OK, {fail} FAIL")

    # 後處理：新生成的 base/lid/mount STL 一律補 GLB（assembly 載入更快、demo/live 一致）
    # 缺少轉換模組屬於環境硬錯誤（hard error），不可降級為 WARN；轉換本身的失敗才當 WARN。
    try:
        from lib.cad.glb_convert import ensure_shell_glbs
    except ImportError as e:
        print(f"  [FAIL] GLB 後處理模組缺失（lib.cad.glb_convert）：{e}")
        raise
    try:
        res = ensure_shell_glbs(SHELLS)
        print(f"GLB 後處理：轉換 {len(res['converted'])}、跳過 {len(res['skipped'])}")
    except Exception as e:
        print(f"  [WARN] GLB 後處理失敗：{e}")
        fail += 1

    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
