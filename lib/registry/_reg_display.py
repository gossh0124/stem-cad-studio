"""Display and lighting component definitions."""
from __future__ import annotations

from .component_spec import ComponentSpec, ConnectorPort, MountingHole


DISPLAY_COMPONENTS: dict[str, ComponentSpec] = {
    'Display-OLED-class': ComponentSpec(
        name='SSD1306 OLED 0.96 inch I2C', class_name='Display-OLED-class',
        tags=['bus:i2c', 'display:graphics'],
        mounting_holes=[
            MountingHole(x=2.5, y=2.5, diameter=2.0), MountingHole(x=24.5, y=2.5, diameter=2.0),
            MountingHole(x=2.5, y=24.5, diameter=2.0), MountingHole(x=24.5, y=24.5, diameter=2.0),
        ],
        ports=[
            ConnectorPort(name='GND',    port_type='GND',   x=5.08,  y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VCC',    port_type='PWR',   x=7.62,  y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='SCL',    port_type='I2C',   x=10.16, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='SDA',    port_type='I2C',   x=12.70, y=0.0,  width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Screen', port_type='OTHER', x=13.5, y=16.0, width=22.0, height=11.0, side='face'),
        ],
    ),
    'Display-LCD-class': ComponentSpec(
        name='LCD 1602 I2C Module', class_name='Display-LCD-class',
        tags=['bus:i2c', 'display:text'],
        mounting_holes=[
            MountingHole(x=2.5, y=2.5, diameter=2.5), MountingHole(x=77.5, y=2.5, diameter=2.5),
            MountingHole(x=2.5, y=33.5, diameter=2.5), MountingHole(x=77.5, y=33.5, diameter=2.5),
        ],
        ports=[
            ConnectorPort(name='GND', port_type='GND', x=2.54,  y=36.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VCC', port_type='PWR', x=5.08,  y=36.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='SDA', port_type='I2C', x=7.62,  y=36.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='SCL', port_type='I2C', x=10.16, y=36.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Screen', port_type='OTHER', x=40.0, y=18.0, width=64.0, height=14.0, side='face'),
        ],
    ),
    'Display-EInk-class': ComponentSpec(
        name='2.9 inch E-Ink Display (SPI)', class_name='Display-EInk-class',
        tags=['bus:spi', 'display:graphics'],
        mounting_holes=[MountingHole(x=3.0, y=3.0, diameter=2.0), MountingHole(x=86.0, y=35.0, diameter=2.0)],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR',  x=2.00,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',  x=4.54,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='DIN',  port_type='SPI',  x=7.08,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='CLK',  port_type='SPI',  x=9.62,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='CS',   port_type='SPI',  x=12.16, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='DC',   port_type='GPIO', x=14.70, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='RST',  port_type='GPIO', x=17.24, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='BUSY', port_type='GPIO', x=19.78, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Screen', port_type='OTHER', x=44.5, y=19.0, width=66.0, height=29.0, side='face'),
        ],
    ),
    'LED-Matrix-class': ComponentSpec(
        name='MAX7219 8x8 LED Matrix Module', class_name='LED-Matrix-class',
        tags=['bus:spi', 'display:dot_matrix'],
        mounting_holes=[MountingHole(x=2.5, y=2.5, diameter=3.0), MountingHole(x=29.5, y=29.5, diameter=3.0)],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR',  x=2.00,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',  x=4.54,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='DIN',  port_type='SPI',  x=7.08,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='CS',   port_type='SPI',  x=9.62,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='CLK',  port_type='SPI',  x=12.16, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Grid', port_type='OTHER', x=16.0, y=16.0, width=20.0, height=20.0, side='face'),
        ],
    ),
    # -- Lighting --
    'Lighting-LED-RGB-class': ComponentSpec(
        name='5mm RGB LED (Common Cathode)', class_name='Lighting-LED-RGB-class',
        tags=['gpio:pwm', 'light:rgb'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='R',   port_type='GPIO', x=0.5, y=0.0, width=1.0, height=1.0, side='face'),
            ConnectorPort(name='GND', port_type='GND',  x=1.8, y=0.0, width=1.0, height=1.0, side='face'),
            ConnectorPort(name='G',   port_type='GPIO', x=3.0, y=0.0, width=1.0, height=1.0, side='face'),
            ConnectorPort(name='B',   port_type='GPIO', x=4.3, y=0.0, width=1.0, height=1.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Lighting-LED-Strip-class': ComponentSpec(
        name='Generic LED Strip 5V (10cm segment)', class_name='Lighting-LED-Strip-class',
        tags=['gpio:digital', 'light:strip'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC', port_type='PWR',  x=2.0, y=5.0, width=3.0, height=2.0, side='left'),
            ConnectorPort(name='GND', port_type='GND',  x=2.0, y=2.0, width=3.0, height=2.0, side='left'),
        ],
        enclosure_relation='panel',
    ),
    'Lighting-NeoPixel-class': ComponentSpec(
        name='WS2812B NeoPixel Strip (8 LEDs)', class_name='Lighting-NeoPixel-class',
        tags=['gpio:digital', 'light:addressable'],
        # B5-coord 2026-06-12: 2 mounting holes from Adafruit NeoPixel-Sticks official EagleCAD
        # .brd (Product 1426), MOUNTINGHOLE_2.0_PLATED pads drill 2.2mm — Tier-A, SSOT-frame verbatim.
        mounting_holes=[MountingHole(x=12.7, y=8.128, diameter=2.2), MountingHole(x=38.1, y=8.128, diameter=2.2)],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR',  x=0.0, y=5.0, width=3.0, height=2.0, side='left'),
            ConnectorPort(name='DIN',  port_type='GPIO', x=0.0, y=2.0, width=3.0, height=2.0, side='left'),
            ConnectorPort(name='GND',  port_type='GND',  x=0.0, y=8.0, width=3.0, height=2.0, side='left'),
        ],
        enclosure_relation='panel',
    ),
    'Lighting-LED-PWM-class': ComponentSpec(
        name='Single PWM-Dimmable LED (5mm)', class_name='Lighting-LED-PWM-class',
        tags=['gpio:pwm', 'light:single'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='Anode',   port_type='GPIO', x=1.5, y=0.0, width=1.0, height=1.0, side='face'),
            ConnectorPort(name='Cathode', port_type='GND',  x=3.0, y=0.0, width=1.0, height=1.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
}
