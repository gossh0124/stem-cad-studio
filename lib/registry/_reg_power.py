"""Power supply and structural component definitions."""
from __future__ import annotations

from .component_spec import ComponentSpec, ConnectorPort, MountingHole


POWER_COMPONENTS: dict[str, ComponentSpec] = {
    # -- Power --
    'USB-5V-class': ComponentSpec(
        name='Generic USB 5V Power Module', class_name='USB-5V-class',
        tags=['iface:passive', 'power:usb_5v'],
        length_mm=60.0, width_mm=30.0, height_mm=18.0,
        mounting_holes=[MountingHole(x=3.0, y=3.0, diameter=2.5), MountingHole(x=57.0, y=27.0, diameter=2.5)],
        ports=[
            ConnectorPort(name='USB-IN',  port_type='USB', x=30.0, y=0.0,  width=14.0, height=6.5, side='bottom'),
            ConnectorPort(name='VCC-OUT', port_type='PWR', x=57.0, y=30.0, width=5.0,  height=4.0, side='face'),
            ConnectorPort(name='GND-OUT', port_type='GND', x=43.0, y=30.0, width=5.0,  height=4.0, side='face'),
        ],
        enclosure_relation='external',
    ),
    'Battery-LiPo-class': ComponentSpec(
        name='1S 1000mAh LiPo Battery', class_name='Battery-LiPo-class',
        tags=['iface:passive', 'power:battery_lipo'],
        length_mm=50.0, width_mm=34.0, height_mm=5.5,
        mounting_holes=[],
        ports=[ConnectorPort(name='JST-PH', port_type='PWR', x=17.0, y=0.0, width=8.0, height=5.0, side='bottom')],
        enclosure_relation='external',
    ),
    'Battery-AA-class': ComponentSpec(
        name='2xAA Battery Holder', class_name='Battery-AA-class',
        tags=['iface:passive', 'power:battery_alkaline'],
        length_mm=59.0, width_mm=32.0, height_mm=15.0,
        mounting_holes=[MountingHole(x=3.0, y=3.0, diameter=2.0), MountingHole(x=56.0, y=29.0, diameter=2.0)],
        ports=[ConnectorPort(name='Wire-Exit', port_type='PWR', x=28.5, y=0.0, width=6.0, height=4.0, side='face')],
        enclosure_relation='external',
    ),
    'AC-Adapter-class': ComponentSpec(
        name='AC-DC 5V 2A Adapter Module', class_name='AC-Adapter-class',
        tags=['iface:passive', 'power:ac_dc'],
        length_mm=50.0, width_mm=30.0, height_mm=20.0,
        current_ma=2000.0,  # supply OUTPUT capacity (kept; differs from POWER_MA consumption=0)
        mounting_holes=[MountingHole(x=3.0, y=3.0, diameter=2.5), MountingHole(x=47.0, y=27.0, diameter=2.5)],
        ports=[
            ConnectorPort(name='AC-IN',  port_type='OTHER', x=0.0,  y=15.0, width=10.0, height=8.0, side='left'),
            ConnectorPort(name='DC-OUT', port_type='PWR',   x=50.0, y=15.0, width=5.0,  height=4.0, side='right'),
        ],
        enclosure_relation='external',
    ),
    'USB-Adapter-class': ComponentSpec(
        name='USB 5V Power Adapter', class_name='USB-Adapter-class',
        tags=['iface:passive', 'power:usb_5v'],
        length_mm=50.0, width_mm=28.0, height_mm=18.0,
        current_ma=1000.0,  # supply OUTPUT capacity (kept; differs from POWER_MA consumption=0)
        mounting_holes=[],
        ports=[
            ConnectorPort(name='USB-OUT', port_type='USB', x=25.0, y=0.0, width=14.0, height=6.5, side='bottom'),
        ],
        enclosure_relation='external',
    ),
    # -- Structural --
    'Chassis-Car-class': ComponentSpec(
        name='Smart Car Chassis (2WD/4WD)', class_name='Chassis-Car-class',
        tags=['iface:passive', 'structure:vehicle_chassis'],
        length_mm=200.0, width_mm=150.0, height_mm=30.0,
        mounting_holes=[
            MountingHole(x=10.0, y=10.0, diameter=3.0),
            MountingHole(x=190.0, y=10.0, diameter=3.0),
            MountingHole(x=10.0, y=140.0, diameter=3.0),
            MountingHole(x=190.0, y=140.0, diameter=3.0),
        ],
        ports=[
            ConnectorPort(name='Motor-L', port_type='OTHER', x=0.0,   y=50.0, width=10.0, height=20.0, side='left'),
            ConnectorPort(name='Motor-R', port_type='OTHER', x=200.0, y=50.0, width=10.0, height=20.0, side='right'),
        ],
    ),
}
