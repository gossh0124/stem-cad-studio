// ═══════════════════════════════════════════
// config/mcu-ports.js — MCU physical pin header layouts
// STR5: extracted from schematic/comp-specs.js
// ═══════════════════════════════════════════

(() => {
  window.MCU_PORTS = {
    Arduino: {
      label: 'Arduino Uno',
      sub: 'ATmega328P',
      north: [],
      south: [],
      west: ['D0/RX', 'D1/TX', 'D2', 'D3', 'D4', 'D5~', 'D6~', 'D7', 'D8', 'D9~', 'D10~', 'D11~', 'D12', 'D13', 'GND_D', 'AREF'],
      east: ['IOREF', 'RESET', '3V3', '5V', 'GND', 'GND2', 'VIN', 'A0', 'A1', 'A2', 'A3', 'A4/SDA', 'A5/SCL'],
    },
    ESP32: {
      label: 'ESP32',
      sub: 'Xtensa LX6 · WiFi+BT',
      // F-S2: north/south expose the remaining real GPIOs the allocator can hand out
      // (D2 strapping, D12-D15 JTAG/strap, D23 SPI MOSI, D1/D3 UART) so wires to them
      // are not silently dropped. Drift-gated by tests/test_mcu_pin_whitelist_drift.py.
      north: ['D1', 'D2', 'D3', 'D12'],
      south: ['D13', 'D14', 'D15', 'D23'],
      west: ['3V3', 'GND', 'D4', 'D5', 'D16', 'D17', 'D18', 'D19', 'D21/SDA', 'D22/SCL'],
      east: ['5V/VIN', 'GND', 'D25', 'D26', 'D27', 'D32', 'D33', 'D34', 'D35', 'D36', 'D39'],
    },
    Microbit: {
      label: 'micro:bit',
      sub: 'nRF52833',
      // F-S2: north/south expose the remaining edge pins the allocator can hand out
      // (P3/P4/P10 analog, P9/P13/P14/P15 incl SPI) so wires are not silently dropped.
      north: ['P3', 'P4', 'P9'],
      south: ['P10', 'P13', 'P14', 'P15'],
      west: ['3V', 'GND', 'P0', 'P1', 'P2'],
      east: ['P8', 'P12', 'P16', 'P19/SCL', 'P20/SDA'],
    },
    RPi: {
      label: 'Raspberry Pi',
      sub: 'BCM2711',
      // F-S2: north/south expose the remaining BCM GPIOs in the allocator pool
      // (GP5-GP11 incl SPI CE/SCK/MISO, GP14/GP15 UART, GP16/GP20/GP21/GP26) so
      // wires to them are not silently dropped. Drift-gated by test_mcu_pin_whitelist_drift.
      north: ['GP5', 'GP6', 'GP7', 'GP8', 'GP9', 'GP10', 'GP11'],
      south: ['GP14', 'GP15', 'GP16', 'GP20', 'GP21', 'GP26'],
      west: ['3V3', '5V', 'GND', 'GP4', 'GP17', 'GP27', 'GP22'],
      east: ['GP12', 'GP13', 'GP18', 'GP19', 'GP23', 'GP24', 'GP25', 'GP2/SDA', 'GP3/SCL'],
    },
  };
})();
