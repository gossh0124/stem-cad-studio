"""tests/test_connector_port_derivation.py — STR14: ConnectorPort 推導管線測試。"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lib.pcb import (
    ARDUINO_UNO_R3, ESP32_DEVKIT_V1, MICROBIT_V2, RASPBERRY_PI_4B,
    derive_connector_port_specs, derive_connector_ports_generic,
)
from lib.registry import COMPONENT_REGISTRY, ConnectorPort

# ── 常數 ────────────────────────────────────────────────────────────────
BOARD_L = 68.58
BOARD_W = 53.34
REQUIRED_KEYS = {'name', 'port_type', 'x', 'y', 'width', 'height', 'side', 'z'}
VALID_PORT_TYPES = {'USB', 'GPIO', 'I2C', 'UART', 'SPI', 'PWR', 'GND',
                    'ANALOG', 'AUDIO', 'EDGE', 'OTHER'}
VALID_SIDES = {'left', 'right', 'top', 'bottom', 'face'}

# MCU class_names — 有 mcu: tag 的元件
_MCU_KEYS = [k for k, v in COMPONENT_REGISTRY.items()
             if any(t.startswith('mcu:') for t in v.tags)]

# 有 ports 的所有 class_names
_PORTED_KEYS = [k for k, v in COMPONENT_REGISTRY.items() if v.ports]


# ════════════════════════════════════════════════════════════════════════
# 1. TestArduinoPortDerivation
# ════════════════════════════════════════════════════════════════════════
class TestArduinoPortDerivation:
    """直接測試 derive_connector_port_specs() 輸出。"""

    @pytest.fixture(scope='class')
    def ports(self):
        return derive_connector_port_specs()

    def test_returns_seven_ports(self, ports):
        assert len(ports) == 7

    def test_usb_b_port(self, ports):
        p = ports[0]
        assert p['name'] == 'USB-B'
        assert p['port_type'] == 'USB'
        assert p['side'] == 'left'
        assert p['width'] == 12.0

    def test_dc_jack_port(self, ports):
        p = ports[1]
        assert p['name'] == 'DC-Jack'
        assert p['port_type'] == 'PWR'
        assert p['side'] == 'left'

    def test_header_groups_are_face(self, ports):
        header_ports = ports[2:]          # 5 個 header groups
        assert len(header_ports) == 5
        for p in header_ports:
            assert p['side'] == 'face', f"{p['name']} 應為 face，實為 {p['side']}"

    def test_all_ports_have_required_fields(self, ports):
        for p in ports:
            missing = REQUIRED_KEYS - set(p.keys())
            assert not missing, f"{p.get('name','?')} 缺少欄位: {missing}"

    def test_port_names_unique(self, ports):
        names = [p['name'] for p in ports]
        assert len(names) == len(set(names)), f"重複名稱: {names}"

    def test_coordinates_within_board(self, ports):
        """Side ports 允許 x=0（左邊緣），header ports x/y 應在板面範圍內。"""
        for p in ports:
            if p['side'] == 'face':
                assert 0 <= p['x'] <= BOARD_L, f"{p['name']} x={p['x']} 超出板長"
                assert 0 <= p['y'] <= BOARD_W, f"{p['name']} y={p['y']} 超出板寬"
            elif p['side'] == 'left':
                assert p['x'] == 0.0, f"{p['name']} left side 應 x=0"
                assert 0 <= p['y'] <= BOARD_W, f"{p['name']} y={p['y']} 超出板寬"


# ════════════════════════════════════════════════════════════════════════
# 2. TestGenericPortDerivation
# ════════════════════════════════════════════════════════════════════════
class TestGenericPortDerivation:
    """測試 derive_connector_ports_generic() 對各 MCU PCBSpec。"""

    def test_esp32_has_usb_port(self):
        ports = derive_connector_ports_generic(ESP32_DEVKIT_V1)
        names = [p['name'] for p in ports]
        assert any('USB' in n for n in names), f"ESP32 未找到 USB port，ports: {names}"

    def test_esp32_port_count(self):
        ports = derive_connector_ports_generic(ESP32_DEVKIT_V1)
        assert len(ports) >= 2, f"ESP32 ports 過少: {len(ports)}"

    def test_microbit_ports(self):
        ports = derive_connector_ports_generic(MICROBIT_V2)
        assert len(ports) >= 1, "Microbit 應有至少 1 個 port"
        for p in ports:
            missing = REQUIRED_KEYS - set(p.keys())
            assert not missing, f"Microbit port {p.get('name','?')} 缺欄位: {missing}"

    def test_rpi_has_multiple_protrusions(self):
        ports = derive_connector_ports_generic(RASPBERRY_PI_4B)
        side_ports = [p for p in ports if p['side'] != 'face']
        assert len(side_ports) >= 3, (
            f"RPi 側邊 port 數量不足 (3+): {len(side_ports)}, "
            f"names={[p['name'] for p in side_ports]}"
        )

    @pytest.mark.parametrize('pcb,label', [
        (ESP32_DEVKIT_V1, 'ESP32'),
        (MICROBIT_V2, 'Microbit'),
        (RASPBERRY_PI_4B, 'RPi'),
    ])
    def test_all_ports_valid_dict_format(self, pcb, label):
        ports = derive_connector_ports_generic(pcb)
        for p in ports:
            missing = REQUIRED_KEYS - set(p.keys())
            assert not missing, f"[{label}] {p.get('name','?')} 缺欄位: {missing}"


# ════════════════════════════════════════════════════════════════════════
# 3. TestRegistryPortExpansion
# ════════════════════════════════════════════════════════════════════════
class TestRegistryPortExpansion:
    """對所有有 ports 的 registry 元件做參數化驗證。"""

    @pytest.mark.parametrize('cn', _PORTED_KEYS)
    def test_all_components_with_ports_valid(self, cn):
        spec = COMPONENT_REGISTRY[cn]
        for p in spec.ports:
            assert p.name, f"[{cn}] port 名稱為空"
            assert p.port_type in VALID_PORT_TYPES, (
                f"[{cn}] {p.name} port_type={p.port_type!r} 不在允許集合"
            )
            assert isinstance(p.x, (int, float)), f"[{cn}] {p.name} x 非數值"
            assert isinstance(p.y, (int, float)), f"[{cn}] {p.name} y 非數值"
            assert isinstance(p.width, (int, float)), f"[{cn}] {p.name} width 非數值"
            assert isinstance(p.height, (int, float)), f"[{cn}] {p.name} height 非數值"
            assert p.side in VALID_SIDES, (
                f"[{cn}] {p.name} side={p.side!r} 不在允許集合"
            )

    @pytest.mark.parametrize('cn', _PORTED_KEYS)
    def test_no_duplicate_port_names(self, cn):
        spec = COMPONENT_REGISTRY[cn]
        names = [p.name for p in spec.ports]
        assert len(names) == len(set(names)), (
            f"[{cn}] 重複 port 名稱: {[n for n in names if names.count(n) > 1]}"
        )

    @pytest.mark.parametrize('cn', _MCU_KEYS)
    def test_mcu_all_have_usb_or_edge(self, cn):
        spec = COMPONENT_REGISTRY[cn]
        has_usb_or_edge = any(
            p.port_type in ('USB', 'EDGE') or 'USB' in p.name
            for p in spec.ports
        )
        assert has_usb_or_edge, (
            f"MCU [{cn}] 沒有 USB 或 EDGE port，"
            f"ports={[(p.name, p.port_type) for p in spec.ports]}"
        )

    def test_panel_components_have_ports(self):
        panel = [(k, v) for k, v in COMPONENT_REGISTRY.items()
                 if v.enclosure_relation == 'panel']
        assert panel, "找不到任何 enclosure_relation='panel' 元件"
        for cn, spec in panel:
            assert spec.ports, f"panel 元件 [{cn}] 沒有 ports"


# ════════════════════════════════════════════════════════════════════════
# 4. TestPortCoordinateConsistency
# ════════════════════════════════════════════════════════════════════════
class TestPortCoordinateConsistency:
    """幾何一致性驗證。"""

    @pytest.mark.parametrize('cn', _PORTED_KEYS)
    def test_port_dimensions_positive(self, cn):
        spec = COMPONENT_REGISTRY[cn]
        for p in spec.ports:
            assert p.width > 0, f"[{cn}] {p.name} width={p.width} 不正"
            assert p.height > 0, f"[{cn}] {p.name} height={p.height} 不正"

    @pytest.mark.parametrize('cn', _PORTED_KEYS)
    def test_side_port_at_edge(self, cn):
        """left side 應 x≈0；right side 應 x≈component length（允差 5mm）。"""
        spec = COMPONENT_REGISTRY[cn]
        for p in spec.ports:
            if p.side == 'left':
                assert p.x <= 5.0, (
                    f"[{cn}] {p.name} side=left 但 x={p.x} 離左邊緣太遠"
                )
            elif p.side == 'right':
                assert p.x >= spec.length_mm - 5.0, (
                    f"[{cn}] {p.name} side=right 但 x={p.x} 離右邊緣太遠 "
                    f"(length={spec.length_mm})"
                )

    @pytest.mark.parametrize('cn', _PORTED_KEYS)
    def test_face_port_z_zero(self, cn):
        spec = COMPONENT_REGISTRY[cn]
        for p in spec.ports:
            if p.side == 'face':
                assert p.z == 0.0, (
                    f"[{cn}] {p.name} face port z={p.z} 應為 0.0"
                )
