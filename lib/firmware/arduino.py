"""
arduino.py — Arduino / ESP32 firmware code generation.
"""
from __future__ import annotations
from datetime import date

from ..wiring import allocate_pins, COMP_LIBS, PinAllocationError
from .templates import match_reactions, OUTPUT_FALLBACK, stem_header_lines


def _gen_arduino(brain: str, outputs: list[str],
                 sensors: list[str], power: str,
                 project_name: str = "", plan: str = "") -> str:

    all_comps = outputs + sensors
    result = allocate_pins(brain, all_comps)
    alloc = result["allocation"]

    def p(comp: str, tag: str) -> object:
        m = alloc.get(comp, {})
        if comp not in alloc:
            raise PinAllocationError(f"Component '{comp}' not found in allocation")
        if tag not in m:
            raise PinAllocationError(f"Tag '{tag}' not found for component '{comp}'")
        return m[tag]

    libs = list(dict.fromkeys(COMP_LIBS.get(k, "") for k in all_comps if k in COMP_LIBS))
    if brain == "ESP32":
        libs.insert(0, "#include <WiFi.h>")

    _GLOBALS = {
        "LED_Single":   lambda k: f"#define LED_PIN {p(k,'+')}",
        "LED_RGB":      lambda k: f"#define LED_R {p(k,'R')}\n#define LED_G {p(k,'G')}\n#define LED_B {p(k,'B')}",
        "NeoPixel":     lambda k: f"#define NEOPIXEL_PIN {p(k,'DIN')}\n#define NEOPIXEL_COUNT 8\nAdafruit_NeoPixel strip(NEOPIXEL_COUNT, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);",
        "Speaker":      lambda k: f"SoftwareSerial dfSerial({p(k,'RX')}, {p(k,'TX')}); // RX={p(k,'RX')}, TX={p(k,'TX')}",
        "Buzzer_Active":  lambda k: f"#define BUZZER_PIN {p(k,'SIG')}",
        "Buzzer_Passive": lambda k: f"#define BUZZER_PIN {p(k,'SIG')}",
        "OLED":         lambda k: f"Adafruit_SSD1306 display(128, 64, &Wire, -1); // I2C SDA={p(k,'SDA')} SCL={p(k,'SCL')}",
        "LCD":          lambda k: f"LiquidCrystal_I2C lcd(0x27, 16, 2); // I2C SDA={p(k,'SDA')} SCL={p(k,'SCL')}",
        "Servo":        lambda k: f"Servo myServo;\n#define SERVO_PIN {p(k,'SIG')}",
        "DCMotor":      lambda k: f"#define MOTOR_EN  {p(k,'ENA')}\n#define MOTOR_IN1 {p(k,'IN1')}\n#define MOTOR_IN2 {p(k,'IN2')}",
        "Stepper":      lambda k: f"#define STEP_IN1 {p(k,'IN1')}\n#define STEP_IN2 {p(k,'IN2')}\n#define STEP_IN3 {p(k,'IN3')}\n#define STEP_IN4 {p(k,'IN4')}\nconst int stepPerRev = 2048;  // 28BYJ-48\nStepper myStepper(stepPerRev, STEP_IN1, STEP_IN3, STEP_IN2, STEP_IN4);",
        "Relay":        lambda k: f"#define RELAY_PIN {p(k,'IN')}",
        "TempHumid":    lambda k: f"#define DHT_PIN {p(k,'DATA')}\n#define DHT_TYPE DHT22\nDHT dht(DHT_PIN, DHT_TYPE);",
        "Ultrasonic":   lambda k: f"#define TRIG_PIN {p(k,'TRIG')}\n#define ECHO_PIN {p(k,'ECHO')}",
        "PIR":          lambda k: f"#define PIR_PIN {p(k,'OUT')}",
        "IR":           lambda k: f"#define IR_PIN {p(k,'OUT')}",
        "SoilMoisture": lambda k: f"#define SOIL_PIN {p(k,'AO')}",
        "Light":        lambda k: f"#define LIGHT_PIN {p(k,'LDR')}",
    }
    globals_ = [_GLOBALS[k](k) for k in all_comps if k in _GLOBALS]

    timer_globals: list[str] = []
    needs_timer = {"LED_Single", "LED_RGB"} & set(outputs)
    has_display = {"OLED", "LCD"} & set(outputs)
    if needs_timer or has_display or sensors:
        timer_globals.append("// ── 非阻塞計時器 ─────────────────────────────────")
        timer_globals.append("unsigned long prevMillis_loop = 0;")
        timer_globals.append("const unsigned long LOOP_INTERVAL = 100;  // 主迴圈節拍 (ms)")
    if "LED_Single" in needs_timer:
        timer_globals.append("unsigned long prevMillis_led = 0;")
        timer_globals.append("bool ledState = false;")
        timer_globals.append("const unsigned long LED_BLINK_INTERVAL = 500;")

    _SETUP = {
        "LED_Single": "  pinMode(LED_PIN, OUTPUT);",
        "LED_RGB":    "  pinMode(LED_R, OUTPUT); pinMode(LED_G, OUTPUT); pinMode(LED_B, OUTPUT);",
        "NeoPixel":   "  strip.begin(); strip.show();",
        "Speaker":    "  dfSerial.begin(9600);",
        "Buzzer_Active":  "  pinMode(BUZZER_PIN, OUTPUT);",
        "Buzzer_Passive": "  pinMode(BUZZER_PIN, OUTPUT);",
        "OLED":       "  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);\n  display.clearDisplay();",
        "LCD":        "  lcd.init(); lcd.backlight();",
        "Servo":      "  myServo.attach(SERVO_PIN);",
        "DCMotor":    "  pinMode(MOTOR_IN1,OUTPUT); pinMode(MOTOR_IN2,OUTPUT); pinMode(MOTOR_EN,OUTPUT);",
        "Stepper":    "  myStepper.setSpeed(10);  // 10 RPM",
        "Relay":      "  pinMode(RELAY_PIN, OUTPUT); digitalWrite(RELAY_PIN, HIGH); // Active-LOW",
        "TempHumid":  "  dht.begin();",
        "Ultrasonic": "  pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);",
        "PIR":        "  pinMode(PIR_PIN, INPUT);",
        "IR":         "  pinMode(IR_PIN, INPUT);",
    }
    setup_lines = [_SETUP[k] for k in all_comps if k in _SETUP]

    loop_lines: list[str] = []
    loop_lines.append("  unsigned long now = millis();")
    loop_lines.append("  if (now - prevMillis_loop < LOOP_INTERVAL) return;")
    loop_lines.append("  prevMillis_loop = now;")
    loop_lines.append("")

    if "TempHumid" in sensors:
        loop_lines.append("  float temp = dht.readTemperature();")
        loop_lines.append("  float humi = dht.readHumidity();")
    if "Ultrasonic" in sensors:
        loop_lines.append("  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2);")
        loop_lines.append("  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);")
        loop_lines.append("  digitalWrite(TRIG_PIN, LOW);")
        loop_lines.append("  float dist_cm = pulseIn(ECHO_PIN, HIGH) * 0.034 / 2.0;")
    if "PIR" in sensors:
        loop_lines.append("  int motion = digitalRead(PIR_PIN);")
    if "IR" in sensors:
        loop_lines.append("  int ir_val = digitalRead(IR_PIN);  // FC-51 LOW=障礙 / VS1838B 脈衝")
    if "SoilMoisture" in sensors:
        loop_lines.append("  int soilPct = map(analogRead(SOIL_PIN), 1023, 0, 0, 100);")
    if "Light" in sensors:
        loop_lines.append("  int lightPct = map(analogRead(LIGHT_PIN), 0, 1023, 100, 0);")

    if sensors:
        loop_lines.append("")

    reactions, handled_outputs = match_reactions(sensors, outputs)
    if reactions:
        loop_lines.append("  // ── 感測→致動規則 ──")
        for r in reactions:
            loop_lines.append(f"  // {r['label']}")
            loop_lines.append(f"  if ({r['condition']}) {{ {r['action']} }}")
            loop_lines.append(f"  else {{ {r['else']} }}")
        loop_lines.append("")

    for o in outputs:
        if o in handled_outputs:
            continue
        if o == "LED_Single":
            loop_lines.append("  // LED 非阻塞閃爍")
            loop_lines.append("  if (now - prevMillis_led >= LED_BLINK_INTERVAL) {")
            loop_lines.append("    prevMillis_led = now;")
            loop_lines.append("    ledState = !ledState;")
            loop_lines.append("    digitalWrite(LED_PIN, ledState);")
            loop_lines.append("  }")
        elif o in ("OLED", "LCD"):
            pass
        else:
            fb = OUTPUT_FALLBACK.get(o)
            if fb:
                loop_lines.append(f"  {fb}")

    if "OLED" in outputs:
        loop_lines.append("")
        loop_lines.append("  // ── OLED 即時顯示 ──")
        loop_lines.append("  display.clearDisplay();")
        loop_lines.append("  display.setTextSize(1);")
        loop_lines.append("  display.setTextColor(WHITE);")
        _oled_y = 0
        if "TempHumid" in sensors:
            loop_lines.append(f'  display.setCursor(0, {_oled_y}); display.print("Temp: "); display.print(temp, 1); display.println(" C");')
            _oled_y += 12
            loop_lines.append(f'  display.setCursor(0, {_oled_y}); display.print("Humi: "); display.print(humi, 0); display.println(" %");')
            _oled_y += 12
        if "SoilMoisture" in sensors:
            loop_lines.append(f'  display.setCursor(0, {_oled_y}); display.print("Soil: "); display.print(soilPct); display.println(" %");')
            _oled_y += 12
        if "Ultrasonic" in sensors:
            loop_lines.append(f'  display.setCursor(0, {_oled_y}); display.print("Dist: "); display.print(dist_cm, 1); display.println(" cm");')
            _oled_y += 12
        if "Light" in sensors:
            loop_lines.append(f'  display.setCursor(0, {_oled_y}); display.print("Light: "); display.print(lightPct); display.println(" %");')
            _oled_y += 12
        if "PIR" in sensors:
            loop_lines.append(f'  display.setCursor(0, {_oled_y}); display.print("Motion: "); display.println(motion ? "YES" : "NO");')
            _oled_y += 12
        if not sensors:
            loop_lines.append('  display.setCursor(0, 0); display.println("CADHLLM Ready");')
        loop_lines.append("  display.display();")

    if "LCD" in outputs:
        loop_lines.append("")
        loop_lines.append("  // ── LCD 即時顯示 ──")
        loop_lines.append("  lcd.clear();")
        if "TempHumid" in sensors:
            loop_lines.append('  lcd.setCursor(0, 0); lcd.print("T:"); lcd.print(temp, 1); lcd.print("C ");')
            loop_lines.append('  lcd.print("H:"); lcd.print(humi, 0); lcd.print("%");')
            if "SoilMoisture" in sensors:
                loop_lines.append('  lcd.setCursor(0, 1); lcd.print("Soil:"); lcd.print(soilPct); lcd.print("%");')
        elif "SoilMoisture" in sensors:
            loop_lines.append('  lcd.setCursor(0, 0); lcd.print("Soil: "); lcd.print(soilPct); lcd.print("%");')
        elif "Ultrasonic" in sensors:
            loop_lines.append('  lcd.setCursor(0, 0); lcd.print("Dist:"); lcd.print(dist_cm, 1); lcd.print("cm");')
        elif "Light" in sensors:
            loop_lines.append('  lcd.setCursor(0, 0); lcd.print("Light:"); lcd.print(lightPct); lcd.print("%");')
        elif "PIR" in sensors:
            loop_lines.append('  lcd.setCursor(0, 0); lcd.print(motion ? "Motion!" : "Clear  ");')
        else:
            loop_lines.append('  lcd.setCursor(0, 0); lcd.print("CADHLLM Ready");')

    if sensors:
        loop_lines.append("")
        loop_lines.append("  // ── Serial 監控 ──")
        _serial_pairs: list[tuple[str, str]] = []
        if "TempHumid" in sensors:
            _serial_pairs.append(("T:", "temp"))
            _serial_pairs.append(("C H:", "humi"))
            _serial_pairs.append(("%", None))
        if "SoilMoisture" in sensors:
            _serial_pairs.append((" Soil:", "soilPct"))
            _serial_pairs.append(("%", None))
        if "Ultrasonic" in sensors:
            _serial_pairs.append((" Dist:", "dist_cm"))
            _serial_pairs.append(("cm", None))
        if "Light" in sensors:
            _serial_pairs.append((" Light:", "lightPct"))
            _serial_pairs.append(("%", None))
        if "PIR" in sensors:
            _serial_pairs.append((" PIR:", "motion"))
        for label, var in _serial_pairs:
            loop_lines.append(f'  Serial.print("{label}");')
            if var:
                loop_lines.append(f"  Serial.print({var});")
        loop_lines.append("  Serial.println();")

    today = date.today().strftime("%Y/%m/%d")
    stem_lines = stem_header_lines(outputs, sensors, project_name, plan, "//")
    return "\n".join([
        "// ═══════════════════════════════════════════════════",
        f"// CADHLLM 自動合成韌體 — {today}",
        f"// Brain: {brain}  Power: {power}",
        f"// Outputs: {', '.join(outputs) or '(無)'}",
        f"// Sensors: {', '.join(sensors) or '(無)'}",
        "// ═══════════════════════════════════════════════════",
        "",
        *stem_lines,
        *libs,
        "",
        "// ── 全域定義 ──────────────────────────────────────",
        *globals_,
        "",
        *timer_globals,
        "",
        "void setup() {",
        "  Serial.begin(9600);",
        *setup_lines,
        '  Serial.println("CADHLLM System Ready");',
        "}",
        "",
        "void loop() {",
        *loop_lines,
        "}",
    ])
