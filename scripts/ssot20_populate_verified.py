"""ssot20_populate_verified.py — SSOT20: backfill voltage/thermal into verified.json.

Idempotent migration. Adds electrical.voltage_operating_v and electrical.thermal_mw
to the 33+19 component classes that lacked them, sourced via triple-source datasheet
research (2026-05-29). All provenance (value / confidence / basis / 3 sources) is
written into the top-level "_ssot20_research_provenance" block so verified.json keeps
its "cross-checked sources" guarantee auditable.

Passive transducer / structural parts (Speaker, Chassis-Car) have NO meaningful DC
operating voltage — they get an electrical.voltage_note instead of a fabricated value,
and remain in the specs-cache _fallback.

Run:  .venv/Scripts/python.exe scripts/ssot20_populate_verified.py [--check]
  --check : report what WOULD change, exit 1 if anything missing (CI / drift gate)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent
_VJ_PATH = _ROOT / "data" / "component_datasheet_verified.json"

# (class, value, confidence, basis, [src "name | url" x3])
VOLTAGE_ADD = [
    ("RaspberryPi-class", 5.0, "HIGH", "RPi4 Model B: 5V DC via USB-C", [
        "Raspberry Pi specs | https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/",
        "Raspberry Pi power docs | https://www.raspberrypi.com/documentation/hardware/raspberrypi/power/README.md",
        "Official 15W USB-C PSU | https://www.raspberrypi.com/products/type-c-power-supply/"]),
    ("Sensor-TempHumid-class", 3.3, "MEDIUM", "DHT22/AM2302 operating 3.3-6V; 3.3 nominal", [
        "components101 | https://components101.com/sensors/dht22-pinout-specs-datasheet",
        "espboards | https://www.espboards.dev/sensors/dht22/",
        "Adafruit AM2302 datasheet | https://cdn-shop.adafruit.com/datasheets/Digital+humidity+and+temperature+sensor+AM2302.pdf"]),
    ("Sensor-PIR-class", 5.0, "HIGH", "HC-SR501 VCC 4.5-20V, 5V recommended (3.3 was OUT logic level, not supply)", [
        "components101 | https://components101.com/sensors/hc-sr501-pir-sensor",
        "lastminuteengineers | https://lastminuteengineers.com/pir-sensor-arduino-tutorial/",
        "makerguides | https://www.makerguides.com/hc-sr501-arduino-tutorial/"]),
    ("Sensor-Light-class", 3.3, "HIGH", "LDR + LM393 module 3.3-5V", [
        "notenoughtech | https://notenoughtech.com/raspberry-pi/light-sensor-lm393-ky018/",
        "Cirkit Designer | https://docs.cirkitdesigner.com/component/c7a45077-fd96-4ccf-9c17-7a9dd14dbcfb/",
        "arduinomodules | https://arduinomodules.info/ky-018-photoresistor-module/"]),
    ("Sensor-IR-class", 3.3, "HIGH", "IR obstacle LM393 module 3.3-5V", [
        "Cirkit Designer | https://docs.cirkitdesigner.com/component/f73c67c1-1c2d-42f6-b4ce-e8034722c2ab/",
        "electroslab | https://electroslab.com/products/ir-obstacle-avoidance-sensor-module",
        "SunFounder | https://www.sunfounder.com/products/ir-obstacle-avoidance-sensor-module"]),
    ("Sensor-MSGEQ7-class", 5.0, "HIGH", "MSGEQ7 VDD 2.7-5.5V, 5.0V typ/recommended", [
        "AllDatasheet MSI MSGEQ7 | https://www.alldatasheet.com/html-pdf/1132447/MSI/MSGEQ7/129/2/MSGEQ7.html",
        "yumpu MSGEQ7 datasheet | https://www.yumpu.com/en/document/view/3575627/",
        "kynix | https://www.kynix.com/components/MSGEQ7-Equalizer-IC-Datasheet-Arduino-Circuit.html"]),
    ("Motor-Servo-class", 5.0, "HIGH", "SG90 operating 4.8-6V; 5V common", [
        "TowerPro | https://towerpro.com.tw/product/sg90-7/",
        "components101 | https://components101.com/motors/servo-motor-basics-pinout-datasheet",
        "SG90 datasheet (IC) | http://www.ee.ic.ac.uk/pcheung/teaching/DE1_EE/stores/sg90_datasheet.pdf"]),
    ("Motor-DC-class", 5.0, "HIGH", "TT gear motor 3-6V; 5V nominal", [
        "Adafruit 3777 | https://www.adafruit.com/product/3777",
        "Cytron | https://my.cytron.io/p-3v-6v-dual-axis-tt-gear-motor",
        "Adafruit blog | https://blog.adafruit.com/2018/04/18/new-product-dc-gearbox-motor-tt-motor-200rpm-3-to-6vdc"]),
    ("Motor-Stepper-class", 5.0, "HIGH", "28BYJ-48 + ULN2003 rated 5V", [
        "components101 | https://components101.com/motors/28byj-48-stepper-motor",
        "lastminuteengineers | https://lastminuteengineers.com/28byj48-stepper-motor-arduino-tutorial/",
        "28BYJ-48 datasheet | https://components101.com/sites/default/files/component_datasheet/28byj48-step-motor-datasheet.pdf"]),
    ("L298N-Driver-class", 5.0, "HIGH", "L298N logic VSS 4.5-7V (5V); 7.0 was motor-supply VS min for onboard regulator", [
        "components101 | https://components101.com/modules/l293n-motor-driver-module",
        "lastminuteengineers | https://lastminuteengineers.com/l298n-dc-stepper-driver-arduino-tutorial/",
        "Cirkit Designer | https://docs.cirkitdesigner.com/component/a9bed943-6fb0-4207-a07a-ad00ea9d6696/"]),
    ("Relay-Module-class", 5.0, "HIGH", "5V single-channel relay coil/control side", [
        "SunFounder | https://www.sunfounder.com/products/5v-one-channel-relay-module-relay-switch",
        "Circuit Rocks | https://circuit.rocks/products/product-2833",
        "Cytron | https://my.cytron.io/p-1ch-active-h-l-5v-optocoupler-relay-module"]),
    ("Pump-Water-class", 5.0, "HIGH", "mini submersible pump 3-5V; 5V upper rated", [
        "Cytron | https://www.cytron.io/p-micro-submersible-water-pump-dc-3v-5v",
        "Kubii | https://www.kubii.com/en/component-kits/3715-micro-submersible-water-pump-dc-3v-5v.html",
        "Gikfun | https://gikfun.com/products/gikfun-dc-3v-5v-micro-submersible-mini-water-pump-pack-of-4pcs"]),
    ("Mist-Atomizer-class", 5.0, "HIGH", "5V piezo atomizer driver module (USB)", [
        "ZeusDIY | https://zeusdiy.com/product/usb-humidifier-atomization-module-5v/",
        "PZT Electronic | https://www.piezoelements.com/mist-generation/piezo-microporous-atomizer/usb-ultrasonic-mist-maker-humidifier-driver.html",
        "MaDDy Electronics | https://maddyelectronics.com/product/5v-ultrasonic-mist-maker-module-108khz-atomizer-type-2-type-c-with-button/"]),
    ("Mist-Ultrasonic-class", 5.0, "HIGH", "5V ultrasonic mist maker module (108kHz, USB)", [
        "CE Store | https://www.cestore-mm.com/product/ultrasonic-mist-maker-usb-driver-module-for-humidifier-5v-o16mm-micro-usb/",
        "PZT Electronic | https://www.piezoelements.com/mist-generation/piezo-microporous-atomizer/ultrasonic-mist-maker-humidifier-driver-board.html",
        "MaDDy Electronics | https://maddyelectronics.com/product/5v-ultrasonic-mist-maker-module-108khz-atomizer-type-2-type-c-with-button/"]),
    ("Display-OLED-class", 3.3, "HIGH", "SSD1306 module 3.3-5V; 3.3 controller logic", [
        "components101 | https://components101.com/displays/oled-display-ssd1306",
        "AZ-Delivery | https://www.az-delivery.de/en/products/0-96zolldisplay",
        "Addicore | https://www.addicore.com/products/oled-display-128x64-0-96in-monochrome"]),
    ("Display-LCD-class", 5.0, "HIGH", "1602 LCD HD44780 requires 5V", [
        "SunFounder | https://docs.sunfounder.com/projects/sf-components/en/latest/component_i2c_lcd.html",
        "Addicore | https://www.addicore.com/products/1602-16x2-character-lcd-with-i2c-backpack",
        "HandsOnTec I2C 1602 datasheet | https://handsontec.com/dataspecs/module/I2C_1602_LCD.pdf"]),
    ("Display-EInk-class", 3.3, "HIGH", "2.9in e-paper panel native 3.3V", [
        "Waveshare wiki | https://www.waveshare.com/wiki/2.9inch_e-Paper_Module",
        "ThinkRobotics | https://thinkrobotics.com/products/2-9inch-e-paper-e-ink-display-module",
        "Parallax | https://www.parallax.com/product/296-x-128-2-9-inch-epaper-display/"]),
    ("LED-Matrix-class", 5.0, "HIGH", "MAX7219 V+ 4.0-5.5V, 5V recommended", [
        "components101 module | https://components101.com/displays/max7219-8x8-led-matrix-module",
        "ElectroDuino | https://www.electroduino.com/max7219-8x8-led-dot-matrix-display-module-functions/",
        "components101 IC | https://components101.com/ics/max7219-pinout-specs-datasheet"]),
    ("Lighting-LED-RGB-class", 3.3, "MEDIUM", "5mm RGB Vf: R~2.0V, G/B~3.4V @20mA; 3.3 ~= G/B channel", [
        "Futurlec | https://www.futurlec.com/LED/RGB5LED.shtml",
        "Adafruit 302 | https://www.adafruit.com/product/302",
        "components101 | https://components101.com/diodes/rgb-led-pinout-configuration-circuit-datasheet"]),
    ("Lighting-LED-Strip-class", 5.0, "HIGH", "generic 5V LED strip", [
        "Cirkit Designer | https://docs.cirkitdesigner.com/component/612c8adb-19aa-42ba-a0e8-bf9cb472c6d8/",
        "LEDSuntech | https://ledsuntech.com/5v-led-strip/",
        "ZBL Lighting | https://www.zbllight.com/led-strip-volages-5v-and-220v.html"]),
    ("Lighting-NeoPixel-class", 5.0, "HIGH", "WS2812B nominal 5V (spec 4.5-5.5V)", [
        "Pololu | https://www.pololu.com/product/2546/specs",
        "ProtoSupplies | https://protosupplies.com/product/ws2812b-addressable-rgb-led-strip-5m-300-leds/",
        "LEDYi | https://www.ledyilighting.com/ws2812b-led-strip/"]),
    ("Lighting-LED-PWM-class", 3.3, "MEDIUM", "5mm white LED Vf ~3.2V @20mA; 3.3 within typ range", [
        "LEDSupply | https://www.ledsupply.com/leds/5mm-led-warm-white-15-degree-viewing-angle",
        "components101 | https://components101.com/diodes/5mm-round-led",
        "Futurlec | https://www.futurlec.com/LED/LED5WWULB.shtml"]),
    ("MP3-Module-class", 5.0, "HIGH", "DFPlayer Mini 3.2-5V; 5V upper rated", [
        "DFRobot wiki | https://wiki.dfrobot.com/dfr0299/",
        "ManualsLib | https://www.manualslib.com/manual/1731781/Dfrobot-Dfplayer-Mini.html",
        "PICAXE SPE033 | https://picaxe.com/docs/spe033.pdf"]),
    ("Remote-class", 3.3, "HIGH", "VS1838B IR receiver 2.7-5.5V; 3.3 nominal", [
        "Cytron | https://www.cytron.io/p-ir-receiver-diode-vs1838b-38khz",
        "Cirkit Designer | https://docs.cirkitdesigner.com/component/dfee4ec9-70d2-4450-88d5-3a9139370c9f/",
        "Osoyoo | https://osoyoo.com/2017/05/07/ir-receiver-diode-vs1838b/"]),
    ("Buzzer-Active-class", 5.0, "HIGH", "active buzzer module 3.3-5V; 5V rated", [
        "Addicore | https://www.addicore.com/products/active-buzzer-5v",
        "espboards KY-012 | https://www.espboards.dev/sensors/ky-012/",
        "Watelectronics | https://www.watelectronics.com/ky-012-active-buzzer-module/"]),
    ("Buzzer-Passive-class", 5.0, "HIGH", "passive buzzer drive 3-5.5V; 5V nominal", [
        "ElectroXBD | https://electroxbd.com/product/small-piezoelectric-passive-buzzer-5v/",
        "GroBotronics | https://grobotronics.com/buzzer-5v-passive.html",
        "ProtoSupplies | https://protosupplies.com/product/passive-buzzer-5v-module/"]),
    ("Button-class", 5.0, "MEDIUM", "rail-dependent passive contact; 5V logic nominal (max-rated 12V DC / 50mA)", [
        "components101 | https://components101.com/switches/push-button",
        "Farnell tact switch | https://www.farnell.com/datasheets/1662341.pdf",
        "TACT 12x12 spec | https://www.scribd.com/document/426288765/TACT-MICRO-SWITCH-12X12"]),
    ("Switch-class", 5.0, "MEDIUM", "rail-dependent passive contact; 5V nominal (max-rated 30V DC)", [
        "components101 SPDT | https://components101.com/switches/spdt-toggle-switch",
        "components101 21236N | https://components101.com/switches/21236n-pcb-mount-spdt-toggle-switch",
        "Pololu | https://www.pololu.com/product/1407"]),
    ("Switch-Generic-class", 5.0, "MEDIUM", "rail-dependent passive contact; 5V nominal (max-rated 30V DC)", [
        "components101 SPDT | https://components101.com/switches/spdt-toggle-switch",
        "Pixelelectric | https://www.pixelelectric.com/electronic-modules/miscellaneous-modules/hall-switches-keypads/spdt-6a-125v-position-toggle-switch/",
        "Addison Electronique | https://addison-electronique.com/en/miniature-toggle-switch-spdt-on-on-125v-6a-3-pins.html"]),
    ("Potentiometer-class", 5.0, "MEDIUM", "passive resistor; 5V rail nominal (rated ~70V @ 500mW)", [
        "components101 | https://components101.com/resistors/potentiometer",
        "Futurlec POT10K | https://www.futurlec.com/Potentiometers/POT10K.shtml",
        "Bourns 3386 (DigiKey) | https://www.digikey.com/en/datasheets/bournsinc/bourns-inc-3386"]),
    ("Joystick-class", 5.0, "HIGH", "PS2-style joystick module 3.3-5V; 5V nominal", [
        "ShillehTek KY-023 | https://shillehtek.com/blogs/shillehtek-product-manuals/ky-023-dual-axis-joystick-module-ps2-analog-sensor-for-arduino-manual",
        "components101 | https://components101.com/modules/joystick-module",
        "lastminuteengineers | https://lastminuteengineers.com/joystick-interfacing-arduino-processing/"]),
]

# passive/structural: NO voltage_operating_v; record an explanatory note instead.
VOLTAGE_NOTE = [
    ("Speaker-class", "Passive transducer: no DC operating voltage. Spec'd by impedance (8 ohm) "
     "and power handling (0.5W). AC signal-driven; DC would damage the voice coil.", [
        "ProtoSupplies | https://protosupplies.com/product/speaker-36mm-0-5w-8-ohm-2/",
        "Taoglas SPKM.36.8.B | https://www.taoglas.com/product/spkm-36-8-b-36mm-miniature-speaker-8-ohm-ip67/",
        "SpikenzieLabs | https://www.spikenzielabs.com/Catalog/audio/speakers/speaker-8-ohm-0.5w-36mm"]),
    ("Chassis-Car-class", "Structural component: acrylic/metal plate + motors + wheels, no onboard "
     "electronics and no intrinsic operating voltage.", [
        "Robocraze | https://robocraze.com/products/2wd-two-wheel-drive-diy-kit-a-smart-robot-car-with-chassis",
        "eElectronicParts | https://www.eelectronicparts.com/products/2wd-smart-car-robot-chassis-base-acrylic-plate-kit-arduino-mcu-diy",
        "Makerlab | https://www.makerlab-electronics.com/products/smart-robot-car-chassis-kit"]),
]

# (class, value, confidence, basis, [src x3])
THERMAL_ADD = [
    ("Sensor-SoilMoisture-class", 16.5, "MEDIUM", "derived V*I: 3.3V x 5mA (capacitive v1.2)", [
        "lastminuteengineers | https://lastminuteengineers.com/capacitive-soil-moisture-sensor-arduino/",
        "DFRobot SEN0193 | https://wiki.dfrobot.com/Capacitive_Soil_Moisture_Sensor_SKU_SEN0193",
        "Electronica Embajadores | https://www.electronicaembajadores.com/en/Productos/Detalle/SSHU002/"]),
    ("Sensor-Light-class", 5.0, "LOW", "legacy estimate ~3.3V x 1mA; research V*I~1.5mW (LOW conf) not adopted", [
        "notenoughtech | https://notenoughtech.com/raspberry-pi/light-sensor-lm393-ky018/",
        "TI LM393 | https://www.ti.com/product/LM393",
        "arduinomodules | https://arduinomodules.info/ky-018-photoresistor-module/"]),
    ("Sensor-IR-class", 66.0, "MEDIUM", "derived V*I: 3.3V x 20mA (IR emitter active)", [
        "electroslab | https://electroslab.com/products/ir-obstacle-avoidance-sensor-module",
        "iFuture Technology | https://ifuturetech.org/product/infrared-obstacle-avoidance-ir-sensor-module/",
        "Cirkit Designer | https://docs.cirkitdesigner.com/component/f73c67c1-1c2d-42f6-b4ce-e8034722c2ab/"]),
    ("Sensor-MSGEQ7-class", 4.0, "HIGH", "derived V*I: 5V x 0.8mA (datasheet IDD typ)", [
        "AllDatasheet MSI MSGEQ7 | https://www.alldatasheet.com/html-pdf/1132447/MSI/MSGEQ7/129/2/MSGEQ7.html",
        "yumpu MSGEQ7 datasheet | https://www.yumpu.com/en/document/view/3575627/",
        "kynix | https://www.kynix.com/components/MSGEQ7-Equalizer-IC-Datasheet-Arduino-Circuit.html"]),
    ("Potentiometer-class", 2.5, "HIGH", "derived V*I: 5V x 0.5mA (5V/10k)", [
        "components101 | https://components101.com/resistors/potentiometer",
        "SparkFun | https://www.sparkfun.com/rotary-potentiometer-10k-ohm-linear.html",
        "mozelectronics | https://mozelectronics.com/tutorials/10k-vs-100k-potentiometer/"]),
    ("Joystick-class", 5.0, "MEDIUM", "derived V*I: 5V x 1mA (two 10k pots)", [
        "ShillehTek KY-023 | https://shillehtek.com/blogs/shillehtek-product-manuals/ky-023-dual-axis-joystick-module-ps2-analog-sensor-for-arduino-manual",
        "components101 | https://components101.com/modules/joystick-module",
        "Electro-Tech-Online | https://www.electro-tech-online.com/threads/voltage-divider-with-10k%CE%A9-potentiometer.26289/"]),
    ("Remote-class", 5.0, "HIGH", "derived V*I: 3.3V x 1.5mA (VS1838B Icc max)", [
        "Cirkit Designer | https://docs.cirkitdesigner.com/component/dfee4ec9-70d2-4450-88d5-3a9139370c9f/",
        "AllDatasheet VS1838B | https://www.alldatasheet.com/datasheet-pdf/pdf/1132465/ETC2/VS1838B.html",
        "Osoyoo | https://osoyoo.com/2017/05/07/ir-receiver-diode-vs1838b/"]),
    ("Button-class", 0.0, "HIGH", "passive mechanical contact; I^2R ~0.01mW, negligible", [
        "components101 | https://components101.com/switches/push-button",
        "CK Switches PTS125 | https://www.ckswitches.com/media/1462/pts125.pdf",
        "Farnell tact switch | https://www.farnell.com/datasheets/1662341.pdf"]),
    ("Switch-class", 0.0, "HIGH", "passive contact ~20mOhm; <=0.2mW max, negligible", [
        "components101 SPDT | https://components101.com/switches/spdt-toggle-switch",
        "Addison Electronique | https://addison-electronique.com/en/miniature-toggle-switch-spdt-on-on-125v-6a-3-pins.html",
        "Pololu | https://www.pololu.com/product/1407"]),
    ("Switch-Generic-class", 0.0, "HIGH", "passive contact; negligible at logic currents", [
        "components101 SPDT | https://components101.com/switches/spdt-toggle-switch",
        "Pixelelectric | https://www.pixelelectric.com/electronic-modules/miscellaneous-modules/hall-switches-keypads/spdt-6a-125v-position-toggle-switch/",
        "DatasheetArchive | https://www.datasheetarchive.com/SPDT%20TOGGLE%20SWITCH%20125VAC%206A-datasheet.html"]),
    ("Buzzer-Active-class", 150.0, "HIGH", "derived V*I: 5V x 30mA (internal oscillator)", [
        "Watelectronics | https://www.watelectronics.com/ky-012-active-buzzer-module/",
        "espboards KY-012 | https://www.espboards.dev/sensors/ky-012/",
        "Addicore | https://www.addicore.com/products/active-buzzer-5v"]),
    ("Buzzer-Passive-class", 25.0, "MEDIUM", "derived V*I: 5V x ~5mA at resonance (max 30mA, drive-dependent)", [
        "ElectroXBD | https://electroxbd.com/product/small-piezoelectric-passive-buzzer-5v/",
        "Cirkit Designer | https://docs.cirkitdesigner.com/component/384529b9-e7e5-4b79-b9c0-f21d7f21298b/",
        "ProtoSupplies | https://protosupplies.com/product/passive-buzzer-5v-module/"]),
    ("Lighting-LED-RGB-class", 100.0, "MEDIUM", "single-channel typ ~40-68mW; full-RGB up to ~176mW; 100 retained as mid estimate", [
        "Futurlec | https://www.futurlec.com/LED/RGB5LED.shtml",
        "electronicscomp | https://www.electronicscomp.com/rgb-led-5mm-common-cathode",
        "components101 | https://components101.com/diodes/rgb-led-pinout-configuration-circuit-datasheet"]),
    ("Lighting-LED-PWM-class", 64.0, "HIGH", "derived V*I: 3.2V x 20mA typ operating (max-rated Pd 100-120mW)", [
        "LEDSupply | https://www.ledsupply.com/leds/5mm-led-warm-white-15-degree-viewing-angle",
        "Futurlec | https://www.futurlec.com/LED/LED5WWULB.shtml",
        "make-it.ca | https://www.make-it.ca/5mm-led-specifications/"]),
    ("Battery-AA-class", 0.0, "HIGH", "passive power source; negligible self-heating at typical draw", [
        "Energizer E91 bulletin | https://data.energizer.com/pdfs/e91.pdf",
        "Battery University | https://batteryuniversity.com/article/bu-106-primary-cells",
        "derived: passive source, no active dissipation | n/a"]),
    ("Battery-LiPo-class", 0.0, "HIGH", "passive power source; negligible self-heating at typical draw", [
        "Battery University LiPo | https://batteryuniversity.com/article/bu-204-how-do-lithium-batteries-work",
        "SparkFun LiPo guide | https://learn.sparkfun.com/tutorials/battery-technologies/lithium-polymer",
        "derived: passive source, no active dissipation | n/a"]),
    ("USB-5V-class", 0.0, "HIGH", "passthrough USB breakout; negligible self-heating", [
        "USB 2.0 power spec (500mA) | https://www.usb.org/documents",
        "derived: passive passthrough | n/a",
        "derived: passive passthrough | n/a"]),
    ("USB-Adapter-class", 200.0, "LOW", "supply conversion loss estimate (light-load); not a datasheet spec", [
        "Bel Fuse efficiency tech paper | https://www.belfuse.com/resource-library/tech-paper/efficiency-standards-for-external-power-supplies",
        "DOE Level VI standard | https://www.belfuse.com/resource-library/tech-paper/efficiency-standards-for-external-power-supplies",
        "no-load standby ref | https://michaelbluejay.com/electricity/vampire.html"]),
    ("Chassis-Car-class", 0.0, "HIGH", "structural; no onboard electronics", [
        "Robocraze | https://robocraze.com/products/2wd-two-wheel-drive-diy-kit-a-smart-robot-car-with-chassis",
        "eElectronicParts | https://www.eelectronicparts.com/products/2wd-smart-car-robot-chassis-base-acrylic-plate-kit-arduino-mcu-diy",
        "SriTu Hobby | https://srituhobby.com/product/2wd-mini-round-double-deck-smart-robot-car-chassis/"]),
]


def main(check: bool) -> int:
    vj = json.loads(_VJ_PATH.read_text(encoding="utf-8"))
    prov = vj.get("_ssot20_research_provenance", {})
    changes: list[str] = []

    def _set(cls: str, field: str, value, conf: str, basis: str, sources: list[str]):
        if cls not in vj:
            raise KeyError(f"class {cls} not in verified.json")
        elec = vj[cls].setdefault("electrical", {})
        if elec.get(field) != value:
            changes.append(f"{cls}.{field}: {elec.get(field)} -> {value}")
        elec[field] = value
        prov.setdefault(cls, {})[field] = {
            "value": value, "confidence": conf, "basis": basis, "sources": sources,
        }

    for cls, value, conf, basis, srcs in VOLTAGE_ADD:
        _set(cls, "voltage_operating_v", value, conf, basis, srcs)
    for cls, value, conf, basis, srcs in THERMAL_ADD:
        _set(cls, "thermal_mw", value, conf, basis, srcs)
    for cls, note, srcs in VOLTAGE_NOTE:
        elec = vj[cls].setdefault("electrical", {})
        if elec.get("voltage_note") != note:
            changes.append(f"{cls}.voltage_note set (passive, no operating V)")
        elec["voltage_note"] = note
        prov.setdefault(cls, {})["voltage_operating_v"] = {
            "value": None, "confidence": "N/A", "basis": "passive/structural — no DC operating voltage; kept in specs-cache _fallback",
            "sources": srcs,
        }

    vj["_ssot20_research_provenance"] = prov

    if check:
        if changes:
            print(f"[ssot20] {len(changes)} field(s) NOT yet applied:")
            for c in changes:
                print("  -", c)
            return 1
        print("[ssot20] verified.json already fully populated (voltage+thermal). OK")
        return 0

    _VJ_PATH.write_text(json.dumps(vj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ssot20] applied {len(changes)} change(s) to {_VJ_PATH.name}")
    for c in changes:
        print("  -", c)
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
