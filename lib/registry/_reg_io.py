"""Control/input and sound component definitions."""
from __future__ import annotations

from .component_spec import ComponentSpec, ConnectorPort, MountingHole


IO_COMPONENTS: dict[str, ComponentSpec] = {
    # -- Buttons & Switches --
    'Button-class': ComponentSpec(
        name='Tactile Push Button 12x12', class_name='Button-class',
        tags=['gpio:digital', 'control:button'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='Pin-A1', port_type='GPIO', x=2.75, y=2.75,  width=1.0, height=1.0, side='face'),
            ConnectorPort(name='Pin-A2', port_type='GPIO', x=2.75, y=9.25,  width=1.0, height=1.0, side='face'),
            ConnectorPort(name='Pin-B1', port_type='GPIO', x=9.25, y=2.75,  width=1.0, height=1.0, side='face'),
            ConnectorPort(name='Pin-B2', port_type='GPIO', x=9.25, y=9.25,  width=1.0, height=1.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Switch-class': ComponentSpec(
        name='Toggle Switch SPDT', class_name='Switch-class',
        tags=['gpio:digital', 'control:switch'],
        mounting_holes=[MountingHole(x=6.5, y=4.0, diameter=6.0)],
        ports=[
            ConnectorPort(name='Toggle-Arm', port_type='OTHER', x=6.5,  y=4.0, width=6.0, height=6.0, side='face'),
            ConnectorPort(name='Term-COM',   port_type='GPIO',  x=3.0,  y=8.0, width=2.5, height=2.5, side='face'),
            ConnectorPort(name='Term-NO',    port_type='GPIO',  x=6.5,  y=8.0, width=2.5, height=2.5, side='face'),
            ConnectorPort(name='Term-NC',    port_type='GPIO',  x=10.0, y=8.0, width=2.5, height=2.5, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Potentiometer-class': ComponentSpec(
        name='Rotary Potentiometer 10K', class_name='Potentiometer-class',
        tags=['gpio:analog', 'control:knob'],
        mounting_holes=[MountingHole(x=8.0, y=8.0, diameter=7.0)],
        ports=[
            ConnectorPort(name='Pin-1', port_type='PWR',    x=4.0,  y=0.0, width=2.0, height=2.0, side='face'),
            ConnectorPort(name='Wiper', port_type='ANALOG', x=8.0,  y=0.0, width=2.0, height=2.0, side='face'),
            ConnectorPort(name='Pin-3', port_type='GND',    x=12.0, y=0.0, width=2.0, height=2.0, side='face'),
            ConnectorPort(name='Shaft', port_type='OTHER',  x=8.0,  y=8.0, width=6.0, height=6.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Joystick-class': ComponentSpec(
        name='Dual-Axis Joystick Module', class_name='Joystick-class',
        tags=['gpio:analog', 'control:joystick'],
        mounting_holes=[MountingHole(x=2.5, y=2.5, diameter=2.5), MountingHole(x=31.5, y=23.5, diameter=2.5)],
        ports=[
            ConnectorPort(name='GND', port_type='GND',    x=2.00,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VCC', port_type='PWR',    x=4.54,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VRx', port_type='ANALOG', x=7.08,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='VRy', port_type='ANALOG', x=9.62,  y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='SW',  port_type='GPIO',   x=12.16, y=0.0, width=2.54, height=2.54, side='face'),
        ],
    ),
    'Switch-Generic-class': ComponentSpec(
        name='Generic Toggle Switch', class_name='Switch-Generic-class',
        tags=['gpio:digital', 'control:switch'],
        mounting_holes=[MountingHole(x=6.5, y=4.0, diameter=6.0)],
        enclosure_relation='panel',
        ports=[
            ConnectorPort(name='Toggle', port_type='OTHER', x=6.5, y=4.0, width=6.0, height=6.0, side='face'),
            ConnectorPort(name='COM',    port_type='GPIO',  x=3.0, y=8.0, width=2.5, height=2.5, side='face'),
            ConnectorPort(name='NO',     port_type='GPIO',  x=10.0, y=8.0, width=2.5, height=2.5, side='face'),
        ],
    ),
    'Remote-class': ComponentSpec(
        name='IR Remote Control Module', class_name='Remote-class',
        tags=['gpio:digital', 'control:ir_remote'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',  port_type='PWR',  x=2.54, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='DATA', port_type='GPIO', x=5.08, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='GND',  port_type='GND',  x=7.62, y=0.0, width=2.54, height=2.54, side='face'),
            ConnectorPort(name='Lens', port_type='OTHER', x=15.0, y=5.0, width=8.0, height=6.0, side='face'),
        ],
        enclosure_relation='external',
    ),
    # -- Sound --
    'Speaker-class': ComponentSpec(
        name='Passive Speaker 36mm', class_name='Speaker-class',
        tags=['iface:passive', 'sound:audio_full'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='Cone',      port_type='AUDIO', x=18.0, y=18.0, width=26.0, height=26.0, side='face'),
            ConnectorPort(name='Wire-Exit', port_type='OTHER', x=18.0, y=0.0,  width=5.0,  height=3.0,  side='bottom'),
        ],
    ),
    'Buzzer-Active-class': ComponentSpec(
        name='Active Buzzer Module 5V', class_name='Buzzer-Active-class',
        tags=['gpio:digital', 'sound:tone_simple'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='SIG', port_type='GPIO', x=2.5, y=0.0, width=2.0, height=2.0, side='face'),
            ConnectorPort(name='VCC', port_type='PWR',  x=6.0, y=0.0, width=2.0, height=2.0, side='face'),
            ConnectorPort(name='GND', port_type='GND',  x=9.5, y=0.0, width=2.0, height=2.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'Buzzer-Passive-class': ComponentSpec(
        name='Passive Buzzer 5V', class_name='Buzzer-Passive-class',
        tags=['gpio:pwm', 'sound:tone_complex'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='SIG', port_type='GPIO', x=4.0, y=0.0, width=2.0, height=2.0, side='face'),
            ConnectorPort(name='GND', port_type='GND',  x=8.0, y=0.0, width=2.0, height=2.0, side='face'),
        ],
        enclosure_relation='panel',
    ),
    'MP3-Module-class': ComponentSpec(
        name='DFPlayer Mini MP3 Module', class_name='MP3-Module-class',
        tags=['bus:uart', 'sound:audio_full'],
        mounting_holes=[],
        ports=[
            ConnectorPort(name='VCC',    port_type='PWR',   x=0.0,  y=18.89, width=2.54, height=2.54, side='left', z=1.0),
            ConnectorPort(name='RX',     port_type='UART',  x=0.0,  y=16.35, width=2.54, height=2.54, side='left', z=1.0),
            ConnectorPort(name='TX',     port_type='UART',  x=0.0,  y=13.81, width=2.54, height=2.54, side='left', z=1.0),
            ConnectorPort(name='DAC_R',  port_type='AUDIO', x=0.0,  y=11.27, width=2.54, height=2.54, side='left', z=1.0),
            ConnectorPort(name='DAC_L',  port_type='AUDIO', x=0.0,  y=8.73,  width=2.54, height=2.54, side='left', z=1.0),
            ConnectorPort(name='SPK1',   port_type='AUDIO', x=0.0,  y=6.19,  width=2.54, height=2.54, side='left', z=1.0),
            ConnectorPort(name='GND',    port_type='GND',   x=0.0,  y=3.65,  width=2.54, height=2.54, side='left', z=1.0),
            ConnectorPort(name='SPK2',   port_type='AUDIO', x=0.0,  y=1.11,  width=2.54, height=2.54, side='left', z=1.0),
            ConnectorPort(name='BUSY',   port_type='GPIO',  x=20.7, y=18.89, width=2.54, height=2.54, side='right', z=1.0),
            ConnectorPort(name='USB-',   port_type='USB',   x=20.7, y=16.35, width=2.54, height=2.54, side='right', z=1.0),
            ConnectorPort(name='USB+',   port_type='USB',   x=20.7, y=13.81, width=2.54, height=2.54, side='right', z=1.0),
            ConnectorPort(name='ADKEY2', port_type='ANALOG',x=20.7, y=11.27, width=2.54, height=2.54, side='right', z=1.0),
            ConnectorPort(name='ADKEY1', port_type='ANALOG',x=20.7, y=8.73,  width=2.54, height=2.54, side='right', z=1.0),
            ConnectorPort(name='IO2',    port_type='GPIO',  x=20.7, y=6.19,  width=2.54, height=2.54, side='right', z=1.0),
            ConnectorPort(name='GND2',   port_type='GND',   x=20.7, y=3.65,  width=2.54, height=2.54, side='right', z=1.0),
            ConnectorPort(name='IO1',    port_type='GPIO',  x=20.7, y=1.11,  width=2.54, height=2.54, side='right', z=1.0),
        ],
    ),
}
