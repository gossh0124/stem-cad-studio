"""scripts/audit_template_gen.py — 驗證 datasheet → WiringTemplate 自動衍生的正確性。

比對自動生成的 template 與手寫 WIRING_TEMPLATES，報告差異。
用途：確保從手寫遷移到自動衍生時零回歸。

用法：.venv/Scripts/python.exe scripts/audit_template_gen.py
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.wiring.engine import WIRING_TEMPLATES, WiringTemplate, WireExtra  # noqa: E402


def _templates_match(m: WiringTemplate, g: WiringTemplate) -> bool:
    """比對兩個 WiringTemplate 是否功能等價（忽略 label）。"""
    if m.vcc != g.vcc:
        return False
    if m.decoupling != g.decoupling:
        return False
    m_pins = {e.tag: (e.comp, e.passive, e.fixed) for e in m.extra}
    g_pins = {e.tag: (e.comp, e.passive, e.fixed) for e in g.extra}
    return m_pins == g_pins


def audit() -> int:
    # -- Import template_gen（graceful fail if module not yet available） --
    try:
        from lib.wiring.template_gen import generate_all_templates, template_from_datasheet
    except ImportError as exc:
        print(
            "lib.wiring.template_gen 尚未建立，無法執行比對。\n"
            f"  ImportError: {exc}\n\n"
            "請等待 template_gen.py 建立完成後再執行此腳本。"
        )
        return 2  # 特殊 exit code：模組缺失

    generated = generate_all_templates()
    manual = WIRING_TEMPLATES

    # ── 1. 覆蓋率 ───────────────────────────────────────────────
    missing = set(manual.keys()) - set(generated.keys())
    extra = set(generated.keys()) - set(manual.keys())

    diff_count = 0
    match_keys: list[str] = []

    # ── 2. 逐元件比對 ───────────────────────────────────────────
    common_keys = sorted(set(manual.keys()) & set(generated.keys()))
    for key in common_keys:
        m = manual[key]
        g = generated[key]
        diffs: list[str] = []

        # 2a. VCC 比對
        if m.vcc != g.vcc:
            diffs.append(f"  vcc: manual={m.vcc} vs generated={g.vcc}")

        # 2b. Label 比對（允許不同，僅報告）
        if m.label != g.label:
            diffs.append(f"  label: manual='{m.label}' vs generated='{g.label}'")

        # 2c. Extra pins 比對
        m_pins = {e.tag: e for e in m.extra}
        g_pins = {e.tag: e for e in g.extra}

        all_tags = sorted(set(m_pins.keys()) | set(g_pins.keys()),
                         key=lambda x: x or "")
        for tag in all_tags:
            if tag not in g_pins:
                diffs.append(f"  pin '{tag}': missing in generated")
            elif tag not in m_pins:
                diffs.append(f"  pin '{tag}': extra in generated")
            else:
                me, ge = m_pins[tag], g_pins[tag]
                if me.comp != ge.comp:
                    diffs.append(f"  pin '{tag}' comp: {me.comp} vs {ge.comp}")
                if me.passive != ge.passive:
                    diffs.append(f"  pin '{tag}' passive: {me.passive} vs {ge.passive}")
                if me.fixed != ge.fixed:
                    diffs.append(f"  pin '{tag}' fixed: {me.fixed} vs {ge.fixed}")

        # 2d. Decoupling 比對
        if m.decoupling != g.decoupling:
            diffs.append(f"  decoupling: manual={m.decoupling} vs generated={g.decoupling}")

        # 區分 label-only diff（可接受）vs pin/vcc/decoupling diff（需修）
        pin_diffs = [d for d in diffs if "label:" not in d]
        if pin_diffs:
            diff_count += 1
            print(f"\nX {key}:")
            for d in diffs:
                print(d)
        elif diffs:
            match_keys.append(key)
            print(f"~  {key}: label 不同（可接受）")
        else:
            match_keys.append(key)
            print(f"OK {key}: 完全一致")

    # ── 3. 已知 bug 修正驗證 ────────────────────────────────────
    print("\n=== Bug Fix 驗證 ===")

    # Decision 6: LDR 應有 vcc="5V"
    g_light = generated.get("Light")
    if g_light and g_light.vcc == "5V":
        print("OK Decision 6: Light/LDR vcc='5V' 正確")
    else:
        vcc_val = g_light.vcc if g_light else "None"
        print(f"FAIL Decision 6: Light/LDR vcc={vcc_val}")

    # Decision 7: DCMotor 不應有重複 GND
    # Decision 9: DCMotor 應有 vcc="5V"
    g_dc = generated.get("DCMotor")
    if g_dc:
        gnd_count = sum(1 for e in g_dc.extra if e.tag == "GND" or e.comp == "GND")
        if gnd_count == 0:
            print("OK Decision 7: DCMotor 無重複 GND extra")
        else:
            print(f"FAIL Decision 7: DCMotor 仍有 {gnd_count} 個 GND extra")
        if g_dc.vcc == "5V":
            print("OK Decision 9: DCMotor vcc='5V' 正確")
        else:
            print(f"FAIL Decision 9: DCMotor vcc={g_dc.vcc}")
    else:
        print("FAIL Decision 7/9: DCMotor 在 generated 中不存在")

    # ── 4. template_from_datasheet 單元件測試 ───────────────────
    print("\n=== template_from_datasheet 抽樣測試 ===")
    spot_check_keys = ["NeoPixel", "Servo", "OLED", "Button"]
    for ck in spot_check_keys:
        result = template_from_datasheet(ck)
        if result is None:
            print(f"FAIL template_from_datasheet('{ck}') 回傳 None")
        elif isinstance(result, WiringTemplate):
            print(f"OK template_from_datasheet('{ck}') 回傳 WiringTemplate")
        else:
            print(f"FAIL template_from_datasheet('{ck}') 型別錯誤: {type(result)}")

    # ── 5. 統計 ─────────────────────────────────────────────────
    total = len(common_keys)
    matched = sum(1 for k in common_keys if _templates_match(manual[k], generated[k]))

    print(f"\n=== 統計 ===")
    print(f"手寫 template: {len(manual)} 個")
    print(f"自動生成: {len(generated)} 個")
    print(f"共同 key: {total} 個")
    print(f"完全一致: {matched}/{total}")
    if missing:
        print(f"缺少（手寫有、自動沒有）: {sorted(missing)}")
    if extra:
        print(f"多出（自動有、手寫沒有）: {sorted(extra)}")

    # ── Exit code ───────────────────────────────────────────────
    if missing or matched < total:
        print(f"\n有差異，請檢查")
        return 1
    print(f"\n全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(audit())
