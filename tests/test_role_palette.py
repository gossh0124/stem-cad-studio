"""ROLE_PALETTE SSOT gate（Wave B）。

role→color 單一 SSOT（lib/config.ROLE_PALETTE）須涵蓋 TAXONOMY 全 11 role;
UI_ROLE_COLOR 衍生自它（修正死碼 'Output'→Actuator）。
"""
from lib.config import ROLE_COLOR_UNKNOWN, ROLE_PALETTE, TAXONOMY_CONFIG
from lib.ui_constants import UI_ROLE_COLOR


def _taxonomy_roles():
    return set(TAXONOMY_CONFIG["core_roles"]) | set(TAXONOMY_CONFIG["aux_roles"])


def test_role_palette_covers_all_taxonomy_roles():
    missing = _taxonomy_roles() - set(ROLE_PALETTE)
    assert not missing, f"ROLE_PALETTE 缺角色: {missing}"


def test_role_palette_colors_distinct_and_no_grey():
    colors = list(ROLE_PALETTE.values())
    assert len(set(colors)) == len(colors), "ROLE_PALETTE 顏色撞色"
    assert ROLE_COLOR_UNKNOWN not in colors, "Unknown 灰不可作 role 色（VS-FALLBACK(b)）"


def test_ui_role_color_derives_from_palette():
    for role, color in ROLE_PALETTE.items():
        assert UI_ROLE_COLOR.get(role) == color, f"{role} 未衍生自 ROLE_PALETTE"
    # 'Output' 死碼正名為 Actuator（保留別名向後相容）
    assert UI_ROLE_COLOR["Output"] == ROLE_PALETTE["Actuator"]
    assert UI_ROLE_COLOR["Unknown"] == ROLE_COLOR_UNKNOWN


def test_frontend_role_palette_matches_config():
    """前端 window.ROLE_PALETTE（component-dimensions.js）須與 config 零漂移。
    手改前端或改 config 未重跑 derive_schematic_tables.py --write 即觸發。"""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from scripts.derive_schematic_tables import derive_role_palette, parse_current_role
    derived = derive_role_palette()
    current = parse_current_role()
    for role, color in derived.items():
        assert current.get(role) == color, \
            f"前端 ROLE_PALETTE.{role}={current.get(role)} vs config={color}"
