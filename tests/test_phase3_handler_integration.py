"""tests/test_phase3_handler_integration.py -- Phase 3 integration & constants tests.

Split from test_phase3_handler.py to stay under 500-line limit.
Coverage targets:
  8. execute() -- full pipeline integration (mocked BOM)
  9. Module-level constants sanity checks
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from copy import deepcopy

from services.phase_handlers.phase3_handler import (
    Phase3Handler,
    _BRAIN_GPIO,
    _BRAIN_BUS,
    _COMPONENT_IO,
    _DISCRETE_COMPONENTS,
    _GPIO_DIRECT_COMPONENTS,
    _GPIO_MAX_MA_PER_PIN,
    _BUS_PROTOCOLS,
)
from services.shared.models import Job, PhaseID
from lib.bom_calculator import BomSummary

# Re-use helpers from the original module
from tests.test_phase3_handler import _make_comp, _basic_bridge


# -- Fixtures --

@pytest.fixture
def handler():
    return Phase3Handler()


@pytest.fixture
def basic_job():
    return Job(job_id="test-001", project_name="TestProject")


# ===============================================================
# 8. execute() -- full pipeline (mocked externals)
# ===============================================================

class TestExecuteIntegration:
    """Full execute() with mocked BOM calculator and file I/O."""

    @pytest.fixture
    def mock_bom(self):
        return BomSummary(
            rows=[
                {"role": "Brain", "type": "Arduino-Uno-class", "label": "Arduino Uno",
                 "qty": 1, "unit_ma": 50.0, "total_ma": 50.0, "unit_ntd": 250, "total_ntd": 250},
                {"role": "Sensor", "type": "Sensor-TempHumid-class", "label": "DHT22",
                 "qty": 1, "unit_ma": 1.5, "total_ma": 1.5, "unit_ntd": 90, "total_ntd": 90},
            ],
            total_ma=51.5,
            total_ntd=340,
            supply_v=5.0,
            power_type="USB-5V-class",
            current_budget_ma=500.0,
        )

    @patch("services.phase_handlers.base._raw_save_bridge")
    @patch("services.phase_handlers.phase3_handler._calculate_bom")
    def test_basic_execute_success(self, mock_calc, mock_save, handler,
                                    basic_job, mock_bom):
        mock_calc.return_value = mock_bom
        mock_save.return_value = "/tmp/bridge.json"

        bridge = _basic_bridge()
        result_bridge, artifacts = handler.execute(basic_job, bridge, None)

        assert artifacts["power_ok"] is True
        assert artifacts["overall_ok"] is True
        assert artifacts["total_ma"] == 51.5
        assert "bom" in result_bridge
        assert "power_budget" in result_bridge

    @patch("services.phase_handlers.base._raw_save_bridge")
    @patch("services.phase_handlers.phase3_handler._calculate_bom")
    def test_power_over_budget_warns(self, mock_calc, mock_save, handler,
                                      basic_job):
        over_bom = BomSummary(
            rows=[{"role": "Brain", "type": "Arduino-Uno-class", "label": "Uno",
                   "qty": 1, "unit_ma": 600.0, "total_ma": 600.0,
                   "unit_ntd": 250, "total_ntd": 250}],
            total_ma=600.0,
            total_ntd=250,
            supply_v=5.0,
            power_type="USB-5V-class",
            current_budget_ma=500.0,
        )
        mock_calc.return_value = over_bom
        mock_save.return_value = None

        bridge = _basic_bridge()
        _, artifacts = handler.execute(basic_job, bridge, None)

        assert artifacts["power_ok"] is False
        assert any("超標" in w for w in artifacts["warnings"])

    @patch("services.phase_handlers.base._raw_save_bridge")
    @patch("services.phase_handlers.phase3_handler._calculate_bom")
    def test_empty_components_raises(self, mock_calc, mock_save, handler, basic_job):
        bridge = {"components": []}
        with pytest.raises(ValueError, match="bridge.components 為空"):
            handler.execute(basic_job, bridge, None)

    @patch("services.phase_handlers.base._raw_save_bridge")
    @patch("services.phase_handlers.phase3_handler._calculate_bom")
    def test_missing_spec_raises(self, mock_calc, mock_save, handler, basic_job):
        bridge = {"components": [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1, "spec": None}
        ]}
        with pytest.raises(ValueError, match="缺少 spec"):
            handler.execute(basic_job, bridge, None)

    @patch("services.phase_handlers.base._raw_save_bridge")
    @patch("services.phase_handlers.phase3_handler._calculate_bom")
    def test_thermal_threshold_triggers_ventilation(self, mock_calc, mock_save,
                                                     handler, basic_job):
        """total_mw > 2000 triggers needs_ventilation."""
        hot_bom = BomSummary(
            rows=[{"role": "Brain", "type": "ESP32-class", "label": "ESP32",
                   "qty": 1, "unit_ma": 450.0, "total_ma": 450.0,
                   "unit_ntd": 180, "total_ntd": 180}],
            total_ma=450.0,  # 450*5=2250mW > 2000
            total_ntd=180,
            supply_v=5.0,
            power_type="USB-5V-class",
            current_budget_ma=500.0,
        )
        mock_calc.return_value = hot_bom
        mock_save.return_value = None

        bridge = _basic_bridge()
        _, artifacts = handler.execute(basic_job, bridge, None)

        assert artifacts["needs_ventilation"] is True
        assert artifacts["total_mw"] == 2250.0

    @patch("services.phase_handlers.base._raw_save_bridge")
    @patch("services.phase_handlers.phase3_handler._calculate_bom")
    def test_ldo_auto_injection(self, mock_calc, mock_save, handler, basic_job):
        """3.3V component on 5V supply triggers LDO injection."""
        mock_calc.return_value = BomSummary(
            rows=[{"role": "Brain", "type": "Arduino-Uno-class", "label": "Uno",
                   "qty": 1, "unit_ma": 50.0, "total_ma": 50.0,
                   "unit_ntd": 250, "total_ntd": 250},
                  {"role": "Display", "type": "Display-OLED-class", "label": "OLED",
                   "qty": 1, "unit_ma": 20.0, "total_ma": 20.0,
                   "unit_ntd": 120, "total_ntd": 120}],
            total_ma=70.0,
            total_ntd=370,
            supply_v=5.0,
            power_type="USB-5V-class",
            current_budget_ma=500.0,
        )
        mock_save.return_value = None

        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Power", "USB-5V-class"),
            _make_comp("Display", "Display-OLED-class"),  # 3.3V needs LDO
        ]
        bridge = _basic_bridge(comps)
        result_bridge, _ = handler.execute(basic_job, bridge, None)

        # LDO should be injected
        types = [c.get("type") for c in result_bridge["components"]]
        assert "LDO-3V3-class" in types
        assert result_bridge["power_budget"]["needs_ldo"] is True

    @patch("services.phase_handlers.base._raw_save_bridge")
    @patch("services.phase_handlers.phase3_handler._calculate_bom")
    def test_progress_callback_receives_messages(self, mock_calc, mock_save,
                                                   handler, basic_job, mock_bom):
        mock_calc.return_value = mock_bom
        mock_save.return_value = None

        messages = []
        bridge = _basic_bridge()
        handler.execute(basic_job, bridge, progress_cb=messages.append)

        assert len(messages) > 0
        assert any("[Phase III]" in m for m in messages)


# ===============================================================
# 9. Module-level constants sanity checks
# ===============================================================

class TestConstants:
    """Sanity checks on module-level lookup dicts."""

    def test_brain_gpio_keys_match_brain_bus(self):
        assert set(_BRAIN_GPIO.keys()) == set(_BRAIN_BUS.keys())

    def test_all_gpio_direct_components_have_positive_ma(self):
        for ctype, ma in _GPIO_DIRECT_COMPONENTS.items():
            assert ma > 0, f"{ctype} has non-positive mA: {ma}"

    def test_discrete_components_is_frozenset(self):
        assert isinstance(_DISCRETE_COMPONENTS, frozenset)

    def test_gpio_max_per_pin_is_20(self):
        assert _GPIO_MAX_MA_PER_PIN == 20.0

    def test_bus_protocols_are_known(self):
        assert _BUS_PROTOCOLS == {"i2c", "spi"}
