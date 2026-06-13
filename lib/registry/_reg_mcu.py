"""MCU board component definitions."""
from __future__ import annotations

from .component_spec import ComponentSpec, ConnectorPort, MountingHole

try:
    from ..pcb import (
        ARDUINO_UNO_R3 as _ARDUINO_PCB,
        ESP32_DEVKIT_V1 as _ESP32_PCB,
        MICROBIT_V2 as _MICROBIT_PCB,
        RASPBERRY_PI_4B as _RPI_PCB,
        derive_connector_port_specs as _arduino_port_specs,
        derive_connector_ports_generic as _generic_port_specs,
    )
except ImportError:
    from pcb import (
        ARDUINO_UNO_R3 as _ARDUINO_PCB,
        ESP32_DEVKIT_V1 as _ESP32_PCB,
        MICROBIT_V2 as _MICROBIT_PCB,
        RASPBERRY_PI_4B as _RPI_PCB,
        derive_connector_port_specs as _arduino_port_specs,
        derive_connector_ports_generic as _generic_port_specs,
    )


MCU_COMPONENTS: dict[str, ComponentSpec] = {
    'Arduino-Uno-class': ComponentSpec(
        name='Arduino Uno R3', class_name='Arduino-Uno-class',
        tags=['bus:usb', 'mcu:8bit'],
        mounting_holes=[MountingHole(x=h.x, y=h.y, diameter=h.diameter)
                        for h in _ARDUINO_PCB.mounting_holes],
        ports=[ConnectorPort(**s) for s in _arduino_port_specs()],
    ),
    'Arduino-Nano-class': ComponentSpec(
        name='Arduino Nano', class_name='Arduino-Nano-class',
        tags=['bus:usb', 'mcu:8bit'],
        # Geometry single-source: pin/header geometry lives in verified.json pin_layout
        # (standard 2x15 @ 2.54mm, community-consensus). No lib/pcb module — schematic/dims
        # derive from SSOT. Registry carries only scalar specs (read-through from cache).
        mounting_holes=[],
        ports=[
            ConnectorPort(name='USB', port_type='USB', x=0.0, y=9.0, width=7.5, height=6.0, side='left'),
            ConnectorPort(name='TOP_HEADER', port_type='OTHER', x=4.72, y=0.0, width=38.1, height=2.5, side='top'),
            ConnectorPort(name='BOTTOM_HEADER', port_type='OTHER', x=4.72, y=18.0, width=38.1, height=2.5, side='bottom'),
        ],
    ),
    'ESP32-class': ComponentSpec(
        name='ESP32 DevKit V1', class_name='ESP32-class',
        tags=['bus:usb', 'mcu:32bit_wifi'],
        mounting_holes=[MountingHole(x=h.x, y=h.y, diameter=h.diameter)
                        for h in _ESP32_PCB.mounting_holes],
        ports=[ConnectorPort(**s) for s in _generic_port_specs(_ESP32_PCB)],
    ),
    'RaspberryPi-class': ComponentSpec(
        name='Raspberry Pi 4 Model B', class_name='RaspberryPi-class',
        tags=['bus:usb', 'mcu:32bit_linux'],
        mounting_holes=[MountingHole(x=h.x, y=h.y, diameter=h.diameter)
                        for h in _RPI_PCB.mounting_holes],
        ports=[ConnectorPort(**s) for s in _generic_port_specs(_RPI_PCB)],
    ),
    'Microbit-class': ComponentSpec(
        name='BBC micro:bit v2', class_name='Microbit-class',
        tags=['bus:usb', 'mcu:edu_block'],
        mounting_holes=[MountingHole(x=h.x, y=h.y, diameter=h.diameter)
                        for h in _MICROBIT_PCB.mounting_holes],
        ports=[ConnectorPort(**s) for s in _generic_port_specs(_MICROBIT_PCB)],
    ),
}
