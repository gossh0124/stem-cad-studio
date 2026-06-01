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
      north: [],
      south: [],
      west: ['3V3', 'GND', 'D4', 'D5', 'D16', 'D17', 'D18', 'D19', 'D21/SDA', 'D22/SCL'],
      east: ['5V/VIN', 'GND', 'D25', 'D26', 'D27', 'D32', 'D33', 'D34', 'D35', 'D36', 'D39'],
    },
    Microbit: {
      label: 'micro:bit',
      sub: 'nRF52833',
      north: [],
      south: [],
      west: ['3V', 'GND', 'P0', 'P1', 'P2'],
      east: ['P8', 'P12', 'P16', 'P19/SCL', 'P20/SDA'],
    },
    RPi: {
      label: 'Raspberry Pi',
      sub: 'BCM2711',
      north: [],
      south: [],
      west: ['3V3', '5V', 'GND', 'GP4', 'GP17', 'GP27', 'GP22'],
      east: ['GP12', 'GP13', 'GP18', 'GP19', 'GP23', 'GP24', 'GP25', 'GP2/SDA', 'GP3/SCL'],
    },
  };
})();
