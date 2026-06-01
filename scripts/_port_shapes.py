"""Shape and color lookup tables for generate_ports_from_dataset.py.

Separated to keep the main script under 500 lines.
"""

# Color defaults by OBC type
TYPE_TO_COLOR = {
    "ic": "#222",
    "connector": "#c9b037",
    "sensor": "#e0e0e0",
    "display": "#1a1a2e",
    "indicator": "#22c55e",
    "passive": "#0066cc",
    "terminal": "#22c55e",
    "heatsink": "#888",
    "mechanical": "#555",
    "button": "#444",
    "module": "#333",
}

# Name-based pattern mapping (highest priority, longest match first)
NAME_TO_SHAPE = {
    # IC packages
    'atmega328p': 'ic-dip',
    'atmega16u2': 'ic-soic',
    'atmega2560': 'ic-qfp',
    'esp32': 'ic-module',
    'ch340': 'ic-soic',
    'ams1117': 'ic-soic',
    'lm393': 'ic-soic',
    'uln2003': 'ic-dip',
    'l298n': 'ic-dip',
    'ne555': 'ic-dip',
    'ssd1306': 'ic-soic',
    'biss0001': 'ic-soic',
    'cd4051': 'ic-dip',
    'msgeq7': 'ic-soic',
    'broadcom': 'ic-qfp',
    'rp2040': 'ic-qfp',
    'nrf51822': 'ic-module',
    'max98357': 'ic-soic',
    # Connectors
    'usb_type_b': 'conn-usb-b',
    'usb_b': 'conn-usb-b',
    'usb_micro': 'conn-usb-micro',
    'micro_usb': 'conn-usb-micro',
    'usb_c': 'conn-usb-c',
    'screw_terminal': 'conn-screw-terminal',
    'terminal_block': 'conn-screw-terminal',
    'barrel_jack': 'conn-barrel-jack',
    'dc_jack': 'conn-barrel-jack',
    'edge_connector': 'conn-header-female',
    'sd_card': 'conn-header-female',
    'header': 'conn-header-male',
    'gpio': 'conn-header-male',
    'icsp': 'conn-header-male',
    'usb': 'conn-usb-micro',
    'jst': 'conn-header-male',
    # Passives
    'electrolytic': 'cap-electrolytic',
    'capacitor': 'cap-ceramic',
    'oscillator': 'crystal-hc49',
    'resonator': 'crystal-hc49',
    'crystal': 'crystal-hc49',
    'inductor': 'res-smd',
    'resistor': 'res-smd',
    'cap': 'cap-ceramic',
    # Active / indicators
    'voltage_reg': 'vreg-to220',
    'regulator': 'vreg-to220',
    'lm7805': 'vreg-to220',
    'power_led': 'led-smd',
    'status_led': 'led-smd',
    'indicator': 'led-smd',
    'led': 'led-smd',
    # Mechanical / interactive
    'trimpot': 'pot-trimmer',
    'trimmer': 'pot-trimmer',
    'sensitivity': 'pot-trimmer',
    'delay': 'pot-trimmer',
    'potentiometer': 'pot-shaft',
    'buzzer': 'buzzer',
    'speaker': 'buzzer',
    'transducer': 'buzzer',
    'fresnel': 'sensor-dome',
    'dome': 'sensor-dome',
    'lens': 'sensor-dome',
    'ldr': 'led-tht',
    'photodiode': 'led-tht',
    'ir_emitter': 'led-tht',
    'ir_receiver': 'led-tht',
    'relay': 'relay',
    'button': 'button-tactile',
    'reset': 'button-tactile',
    'boot': 'button-tactile',
    'switch': 'button-tactile',
    # Motors
    'stepper': 'motor-stepper',
    'servo': 'motor-servo',
    'motor': 'motor-dc',
    'shaft': 'motor-dc',
    # Displays (keep as box)
    'display': 'box',
    'screen': 'box',
    'oled': 'box',
    'lcd': 'box',
    'eink': 'box',
}

# Type-based fallback (lower priority)
TYPE_FALLBACK = {
    'ic': 'ic-soic',
    'connector': 'conn-header-male',
    'sensor': 'res-smd',
    'display': 'box',
    'indicator': 'led-smd',
    'passive': 'cap-ceramic',
    'terminal': 'conn-screw-terminal',
    'heatsink': 'box',
    'mechanical': 'box',
    'button': 'button-tactile',
    'module': 'ic-module',
}

# Pre-sorted by pattern length (longest first) for _infer_shape
_SORTED_NAME_PATTERNS = sorted(NAME_TO_SHAPE.items(), key=lambda x: -len(x[0]))


def infer_shape(name, comp_type, explicit_shape=None):
    """Map OBC entry to detailed shape type."""
    if explicit_shape and explicit_shape not in ('box', 'cylinder', 'dome'):
        return explicit_shape  # already a detailed shape

    nl = name.lower().replace(' ', '_').replace('-', '_')

    for pattern, shape in _SORTED_NAME_PATTERNS:
        if pattern in nl:
            return shape

    return TYPE_FALLBACK.get(comp_type, 'box')


def infer_color(comp_type, explicit_color=None):
    """Return color for an OBC entry."""
    if explicit_color:
        return explicit_color
    return TYPE_TO_COLOR.get(comp_type, "#888")
