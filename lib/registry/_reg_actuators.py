"""Actuator component definitions (motors, relay, pump, mist)."""
from __future__ import annotations

from .component_spec import ComponentSpec, ConnectorPort, MountingHole


ACTUATOR_COMPONENTS: dict[str, ComponentSpec] = {
    'Motor-Servo-class': ComponentSpec(
        name='SG90 Micro Servo Motor', class_name='Motor-Servo-class',
        tags=['gpio:pwm', 'actuate:rotation_position'],
        mounting_holes=[MountingHole(x=2.25, y=6.1, diameter=2.0), MountingHole(x=20.75, y=6.1, diameter=2.0)],
        ports=[
            ConnectorPort(name='GND',    port_type='GND',   x=1.50, y=12.2, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VCC',    port_type='PWR',   x=4.04, y=12.2, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='SIGNAL', port_type='GPIO',  x=6.58, y=12.2, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Shaft',  port_type='OTHER', x=6.5, y=6.1,  width=6.0,  height=6.0,  side='face'),
        ],
    ),
    'Motor-DC-class': ComponentSpec(
        name='DC Gear Motor 3-6V', class_name='Motor-DC-class',
        tags=['gpio:pwm', 'actuate:rotation_continuous'],
        # B5-coord 2026-06-12: 3 mounting holes extracted from Adafruit 3777 TT-motor
        # official STEP (Tier-A). Frame: SSOT_x = STEP_Z + 54.6 (can=x0, shaft=x70 per
        # Shaft port), SSOT_y = STEP_X + 11.2. 2 body holes (x=34) + 1 tab hole at shaft end.
        mounting_holes=[MountingHole(x=34.0, y=2.4, diameter=3.0),
                        MountingHole(x=68.6, y=11.2, diameter=3.0),
                        MountingHole(x=34.0, y=20.0, diameter=3.0)],
        ports=[
            ConnectorPort(name='M+',    port_type='PWR',   x=3.0,  y=22.0, width=4.0, height=3.0, side='face'),
            ConnectorPort(name='M-',    port_type='GND',   x=10.0, y=22.0, width=4.0, height=3.0, side='face'),
            ConnectorPort(name='Shaft', port_type='OTHER', x=70.0, y=11.0, width=8.0, height=8.0, side='right', z=5.0),
        ],
    ),
    'Relay-Module-class': ComponentSpec(
        name='5V Single Channel Relay Module', class_name='Relay-Module-class',
        tags=['gpio:digital', 'actuate:switch_load'],
        mounting_holes=[MountingHole(x=2.5, y=2.5, diameter=3.0), MountingHole(x=47.5, y=2.5, diameter=3.0)],
        ports=[
            ConnectorPort(name='VCC', port_type='PWR',   x=2.54,  y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND', port_type='GND',   x=5.08,  y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='IN',  port_type='GPIO',  x=7.62,  y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='COM', port_type='OTHER', x=31.92, y=26.0, width=5.0,  height=4.0,  side='top'),
            ConnectorPort(name='NO',  port_type='OTHER', x=37.00, y=26.0, width=5.0,  height=4.0,  side='top'),
            ConnectorPort(name='NC',  port_type='OTHER', x=42.08, y=26.0, width=5.0,  height=4.0,  side='top'),
        ],
    ),
    'Pump-Water-class': ComponentSpec(
        name='Mini Submersible Water Pump 3-5V', class_name='Pump-Water-class',
        tags=['gpio:digital', 'actuate:fluid'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',    port_type='PWR',   x=5.0,  y=30.0, width=3.0, height=3.0, side='face'),
            ConnectorPort(name='GND',    port_type='GND',   x=12.0, y=30.0, width=3.0, height=3.0, side='face'),
            ConnectorPort(name='Outlet', port_type='OTHER', x=22.5, y=15.0, width=8.0, height=8.0, side='face'),
        ],
        enclosure_relation='embedded',
        host_structure={
            "kind": "water_tank",
            "dimensions": {"length_mm": 80.0, "width_mm": 60.0, "height_mm": 50.0},
            "entry_port": {"face": "top", "u": 0.5, "v": 0.5},
            "cavity": {"depth_mm": 25.0, "diam_mm": None, "length_mm": 45.0, "width_mm": 30.0},
            "wire_entry": {"face": "back", "u": 0.9, "v": 0.5, "hole_diam_mm": 6.0},
        },
    ),
    'Motor-Stepper-class': ComponentSpec(
        name='28BYJ-48 Stepper Motor + ULN2003', class_name='Motor-Stepper-class',
        tags=['gpio:digital', 'actuate:rotation_position'],
        length_mm=42.0, width_mm=35.0, height_mm=30.0,
        mounting_holes=[MountingHole(x=5.0, y=5.0, diameter=4.0), MountingHole(x=37.0, y=5.0, diameter=4.0)],
        ports=[
            ConnectorPort(name='IN1',  port_type='GPIO', x=5.00,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='IN2',  port_type='GPIO', x=7.54,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='IN3',  port_type='GPIO', x=10.08, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='IN4',  port_type='GPIO', x=12.62, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VCC',  port_type='PWR',  x=15.16, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',  x=17.70, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Shaft', port_type='OTHER', x=21.0, y=17.5, width=5.0, height=5.0, side='face'),
        ],
    ),
    'L298N-Driver-class': ComponentSpec(
        name='L298N Dual H-Bridge Motor Driver Module', class_name='L298N-Driver-class',
        tags=['gpio:pwm', 'actuate:rotation_continuous'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='ENA',  port_type='GPIO', x=16.00, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='IN1',  port_type='GPIO', x=18.54, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='IN2',  port_type='GPIO', x=21.08, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='IN3',  port_type='GPIO', x=23.62, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='IN4',  port_type='GPIO', x=26.16, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='ENB',  port_type='GPIO', x=28.70, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VCC',  port_type='PWR',  x=2.00,  y=0.0,  width=5.08, height=5.08, side='face'),
            ConnectorPort(name='GND',  port_type='GND',  x=7.08,  y=0.0,  width=5.08, height=5.08, side='face'),
            ConnectorPort(name='5V',   port_type='PWR',  x=12.16, y=0.0,  width=5.08, height=5.08, side='face'),
            ConnectorPort(name='OUT1', port_type='OTHER', x=3.00,  y=43.0, width=5.08, height=5.08, side='top'),
            ConnectorPort(name='OUT2', port_type='OTHER', x=8.08,  y=43.0, width=5.08, height=5.08, side='top'),
            ConnectorPort(name='OUT3', port_type='OTHER', x=29.84, y=43.0, width=5.08, height=5.08, side='top'),
            ConnectorPort(name='OUT4', port_type='OTHER', x=34.92, y=43.0, width=5.08, height=5.08, side='top'),
        ],
    ),
    'Mist-Atomizer-class': ComponentSpec(
        name='Piezoelectric Mist Atomizer 20mm', class_name='Mist-Atomizer-class',
        tags=['gpio:digital', 'actuate:mist'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR', x=5.0,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND', x=12.0, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Disc', port_type='OTHER', x=12.5, y=12.5, width=20.0, height=20.0, side='face'),
        ],
        enclosure_relation='embedded',
        host_structure={
            "kind": "water_tank",
            "dimensions": {"length_mm": 80.0, "width_mm": 60.0, "height_mm": 40.0},
            "entry_port": {"face": "top", "u": 0.5, "v": 0.5},
            "cavity": {"depth_mm": 15.0, "diam_mm": 23.0, "length_mm": None, "width_mm": None},
            "wire_entry": {"face": "back", "u": 0.9, "v": 0.5, "hole_diam_mm": 6.0},
        },
    ),
    'Mist-Ultrasonic-class': ComponentSpec(
        name='Ultrasonic Mist Maker Module', class_name='Mist-Ultrasonic-class',
        tags=['gpio:digital', 'actuate:mist'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR', x=5.0,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND', x=15.0, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Disc', port_type='OTHER', x=17.5, y=17.5, width=25.0, height=25.0, side='face'),
        ],
        enclosure_relation='embedded',
        host_structure={
            "kind": "water_tank",
            "dimensions": {"length_mm": 120.0, "width_mm": 80.0, "height_mm": 60.0},
            "entry_port": {"face": "top", "u": 0.5, "v": 0.5},
            "cavity": {"depth_mm": 20.0, "diam_mm": 28.0, "length_mm": None, "width_mm": None},
            "wire_entry": {"face": "back", "u": 0.9, "v": 0.5, "hole_diam_mm": 8.0},
        },
    ),
}
