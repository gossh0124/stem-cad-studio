"""Sensor component definitions."""
from __future__ import annotations

from .component_spec import ComponentSpec, ConnectorPort, MountingHole


SENSOR_COMPONENTS: dict[str, ComponentSpec] = {
    'Sensor-Ultrasonic-class': ComponentSpec(
        name='HC-SR04 Ultrasonic Sensor', class_name='Sensor-Ultrasonic-class',
        tags=['gpio:pulse', 'measure:distance'],
        length_mm=45.0, width_mm=20.0, height_mm=15.0,
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',    port_type='PWR',   x=6.35,  y=20.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='TRIG',   port_type='GPIO',  x=8.89,  y=20.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='ECHO',   port_type='GPIO',  x=11.43, y=20.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',    port_type='GND',   x=13.97, y=20.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='TX-Eye', port_type='OTHER', x=10.0,  y=10.0, width=16.0, height=12.0, side='face'),
            ConnectorPort(name='RX-Eye', port_type='OTHER', x=35.0,  y=10.0, width=16.0, height=12.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Sensor-PIR-class': ComponentSpec(
        name='HC-SR501 PIR Motion Sensor', class_name='Sensor-PIR-class',
        tags=['gpio:digital', 'measure:motion'],
        length_mm=32.0, width_mm=24.0, height_mm=25.0,
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR',   x=13.46, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='OUT',  port_type='GPIO',  x=16.00, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',   x=18.54, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Dome', port_type='OTHER', x=16.0, y=12.0, width=23.0, height=23.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Sensor-TempHumid-class': ComponentSpec(
        name='DHT22 Temperature Humidity Sensor', class_name='Sensor-TempHumid-class',
        tags=['gpio:digital', 'measure:temperature', 'measure:humidity'],
        length_mm=25.1, width_mm=15.1, height_mm=7.7,
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR',   x=3.81,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='DATA', port_type='GPIO',  x=6.35,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='NC',   port_type='OTHER', x=8.89,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',   x=11.43, y=0.0, width=2.54, height=2.54, side='face'),
        ],
    ),
    'Sensor-SoilMoisture-class': ComponentSpec(
        name='Capacitive Soil Moisture Sensor v1.2', class_name='Sensor-SoilMoisture-class',
        tags=['gpio:analog', 'measure:soil_moisture'],
        length_mm=98.0, width_mm=23.0, height_mm=3.5,
        mounting_holes=[MountingHole(x=3.0, y=3.0, diameter=2.0)],
        ports=[
            ConnectorPort(name='AOUT', port_type='ANALOG', x=93.0, y=8.96,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VCC',  port_type='PWR',    x=93.0, y=11.50, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',    x=93.0, y=14.04, width=2.54, height=2.54, side='face'),
        ],
        enclosure_relation='external',
    ),
    'Sensor-Light-class': ComponentSpec(
        name='LDR Photoresistor Module', class_name='Sensor-Light-class',
        tags=['gpio:analog', 'measure:light'],
        length_mm=30.0, width_mm=15.0, height_mm=7.0,
        mounting_holes=[],
        ports=[
            ConnectorPort(name='AOUT', port_type='ANALOG', x=8.73,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='DOUT', port_type='GPIO',   x=11.27, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VCC',  port_type='PWR',    x=13.81, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',    x=16.35, y=0.0, width=2.54, height=2.54, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Sensor-IR-class': ComponentSpec(
        name='IR Obstacle Avoidance Sensor', class_name='Sensor-IR-class',
        tags=['gpio:digital', 'measure:obstacle'],
        length_mm=32.0, width_mm=14.0, height_mm=10.0,
        mounting_holes=[MountingHole(x=3.0, y=7.0, diameter=3.0)],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR',  x=2.00, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='OUT',  port_type='GPIO', x=4.54, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',  x=7.08, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Lens', port_type='OTHER', x=16.0, y=7.0, width=10.0, height=8.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Sensor-MSGEQ7-class': ComponentSpec(
        name='MSGEQ7 Graphic Equalizer (7-band)', class_name='Sensor-MSGEQ7-class',
        tags=['gpio:analog', 'measure:audio_freq'],
        length_mm=9.5, width_mm=6.35, height_mm=3.3,
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',    port_type='PWR',    x=2.0,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',    port_type='GND',    x=6.0,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='OUT',    port_type='ANALOG', x=10.0, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='STROBE', port_type='GPIO',   x=2.0,  y=8.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='RESET',  port_type='GPIO',   x=6.0,  y=8.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='AUDIO',  port_type='OTHER',  x=10.0, y=8.0, width=2.54, height=2.54, side='top'),
        ],
        enclosure_relation='breadboard',
    ),
}
