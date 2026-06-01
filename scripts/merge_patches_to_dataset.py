"""Merge on_board_components patches into component_datasheet_verified.json."""
import json, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(ROOT, "data", "component_datasheet_verified.json")
PATCHES = [
    os.path.join(ROOT, "data", "_patch_mcu.json"),
    os.path.join(ROOT, "data", "_patch_sensor_display.json"),
    os.path.join(ROOT, "data", "_patch_motor_audio_power.json"),
]

def merge():
    with open(DATASET, "r", encoding="utf-8") as f:
        ds = json.load(f)

    stats = {"obc_added": 0, "pin_fixed": 0, "skipped": 0}

    for pf in PATCHES:
        if not os.path.exists(pf):
            print(f"  SKIP missing: {pf}")
            continue
        with open(pf, "r", encoding="utf-8") as f:
            patch = json.load(f)

        for comp_key, patch_data in patch.items():
            if comp_key == "_meta":
                continue
            if comp_key not in ds:
                print(f"  WARN: {comp_key} not in dataset, skipping")
                stats["skipped"] += 1
                continue

            # Merge on_board_components
            obc = patch_data.get("on_board_components", [])
            if obc:
                ds[comp_key]["on_board_components"] = obc
                stats["obc_added"] += 1

            # Merge pin_xy_fixes
            fixes = patch_data.get("pin_xy_fixes", {})
            if fixes:
                hg = ds[comp_key].get("pin_layout", {}).get("header_groups", [])
                for fix_name, fix_data in fixes.items():
                    matched = False
                    for i, g in enumerate(hg):
                        if g.get("name") == fix_name:
                            # Merge pins with XY into existing group
                            fix_pins = fix_data.get("pins", [])
                            # Handle Microbit special format (large_pins + small_pins)
                            if not fix_pins and "large_pins" in fix_data:
                                fix_pins = fix_data.get("large_pins", []) + fix_data.get("small_pins", [])
                            if fix_pins:
                                hg[i]["pins"] = fix_pins
                                hg[i]["pin_count"] = len(fix_pins)
                                if "start_x_mm" in fix_data:
                                    hg[i]["start_x_mm"] = fix_data["start_x_mm"]
                                if "start_y_mm" in fix_data:
                                    hg[i]["start_y_mm"] = fix_data["start_y_mm"]
                                if "side" in fix_data:
                                    hg[i]["side"] = fix_data["side"]
                            matched = True
                            stats["pin_fixed"] += 1
                            break
                    if not matched:
                        # Add as new header group
                        new_group = dict(fix_data)
                        new_group["name"] = fix_name
                        # Handle special formats
                        if "large_pins" in new_group and "pins" not in new_group:
                            new_group["pins"] = new_group.pop("large_pins", []) + new_group.pop("small_pins", [])
                            new_group["pin_count"] = len(new_group["pins"])
                        if "pins" not in new_group:
                            new_group["pins"] = []
                            new_group["pin_count"] = 0
                        hg.append(new_group)
                        if "pin_layout" not in ds[comp_key]:
                            ds[comp_key]["pin_layout"] = {}
                        ds[comp_key]["pin_layout"]["header_groups"] = hg
                        stats["pin_fixed"] += 1

    # Write back
    with open(DATASET, "w", encoding="utf-8") as f:
        json.dump(ds, f, indent=2, ensure_ascii=False)

    print(f"\nMerge complete:")
    print(f"  on_board_components added: {stats['obc_added']}")
    print(f"  pin_xy groups fixed: {stats['pin_fixed']}")
    print(f"  skipped: {stats['skipped']}")

if __name__ == "__main__":
    merge()
