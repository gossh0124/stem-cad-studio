"""test_code_templates.py — Per-component Arduino/C++ test code generators.

Each _tc_* function takes a pin_map dict and returns
{"lang": "cpp", "code": "<sketch source>"}.

TEST_TEMPLATES maps normalized component role name -> generator function.
Imported by templates.py and re-exported for backward compatibility.
"""
from __future__ import annotations


def _tc_neopixel(pin_map):
    pin = pin_map.get("DIN", "?")
    return {
        "lang": "cpp",
        "code": f"""#include <Adafruit_NeoPixel.h>
#define PIN {pin}
#define COUNT 8
Adafruit_NeoPixel strip(COUNT, PIN, NEO_GRB + NEO_KHZ800);

void setup() {{
  strip.begin();
  strip.fill(strip.Color(0, 150, 255));
  strip.show();
}}

void loop() {{
  for (int i = 0; i < COUNT; i++) {{
    strip.setPixelColor(i, strip.Color(0, 255, 0));
    strip.show();
    delay(100);
    strip.setPixelColor(i, strip.Color(0, 0, 0));
  }}
}}""",
    }

def _tc_dht(pin_map):
    pin = pin_map.get("DATA", "?")
    return {
        "lang": "cpp",
        "code": f"""#include <DHT.h>
#define DHT_PIN {pin}
#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);

void setup() {{
  Serial.begin(9600);
  dht.begin();
}}

void loop() {{
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  Serial.print("Temp: "); Serial.print(t);
  Serial.print("C  Humi: "); Serial.print(h);
  Serial.println("%");
  delay(2000);
}}""",
    }

def _tc_ultra(pin_map):
    trig = pin_map.get("TRIG", "?")
    echo = pin_map.get("ECHO", "?")
    return {
        "lang": "cpp",
        "code": f"""#define TRIG {trig}
#define ECHO {echo}

void setup() {{
  Serial.begin(9600);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
}}

void loop() {{
  digitalWrite(TRIG, LOW); delayMicroseconds(2);
  digitalWrite(TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  float cm = pulseIn(ECHO, HIGH) * 0.034 / 2.0;
  Serial.print("Distance: "); Serial.print(cm); Serial.println(" cm");
  delay(500);
}}""",
    }

def _tc_pir(pin_map):
    pin = pin_map.get("OUT", "?")
    return {
        "lang": "cpp",
        "code": f"""#define PIR_PIN {pin}

void setup() {{
  Serial.begin(9600);
  pinMode(PIR_PIN, INPUT);
  Serial.println("Warming up PIR...");
  delay(2000);
}}

void loop() {{
  if (digitalRead(PIR_PIN)) {{
    Serial.println("Motion detected!");
  }}
  delay(200);
}}""",
    }

def _tc_servo(pin_map):
    pin = pin_map.get("SIG", "?")
    return {
        "lang": "cpp",
        "code": f"""#include <Servo.h>
Servo myServo;
#define SERVO_PIN {pin}

void setup() {{
  myServo.attach(SERVO_PIN);
}}

void loop() {{
  myServo.write(0);   delay(1000);
  myServo.write(90);  delay(1000);
  myServo.write(180); delay(1000);
}}""",
    }

def _tc_led(pin_map):
    pin = pin_map.get("+", "?")
    return {
        "lang": "cpp",
        "code": f"""#define LED_PIN {pin}

void setup() {{ pinMode(LED_PIN, OUTPUT); }}
void loop() {{
  digitalWrite(LED_PIN, HIGH); delay(500);
  digitalWrite(LED_PIN, LOW);  delay(500);
}}""",
    }

def _tc_buzzer(pin_map):
    pin = pin_map.get("SIG", "?")
    return {
        "lang": "cpp",
        "code": f"""#define BUZZER {pin}

void setup() {{ pinMode(BUZZER, OUTPUT); }}
void loop() {{
  tone(BUZZER, 440, 200); delay(300);
  tone(BUZZER, 880, 200); delay(300);
  noTone(BUZZER); delay(500);
}}""",
    }

def _tc_soil(pin_map):
    pin = pin_map.get("AO", "?")
    return {
        "lang": "cpp",
        "code": f"""#define SOIL_PIN {pin}

void setup() {{ Serial.begin(9600); }}
void loop() {{
  int val = analogRead(SOIL_PIN);
  Serial.print("Moisture: "); Serial.println(val);
  delay(1000);
}}""",
    }

def _tc_light(pin_map):
    pin = pin_map.get("LDR", "?")
    return {
        "lang": "cpp",
        "code": f"""#define LDR_PIN {pin}

void setup() {{ Serial.begin(9600); }}
void loop() {{
  int lux = analogRead(LDR_PIN);
  Serial.print("Light: "); Serial.println(lux);
  delay(500);
}}""",
    }

def _tc_rgb(pin_map):
    r = pin_map.get("R", "?")
    g = pin_map.get("G", "?")
    b = pin_map.get("B", "?")
    return {
        "lang": "cpp",
        "code": f"""#define LED_R {r}
#define LED_G {g}
#define LED_B {b}

void setup() {{
  pinMode(LED_R, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(LED_B, OUTPUT);
}}
void loop() {{
  analogWrite(LED_R, 255); delay(500);
  analogWrite(LED_R, 0);
  analogWrite(LED_G, 255); delay(500);
  analogWrite(LED_G, 0);
  analogWrite(LED_B, 255); delay(500);
  analogWrite(LED_B, 0);
}}""",
    }

def _tc_stepper(pin_map):
    in1 = pin_map.get("IN1", "?")
    in2 = pin_map.get("IN2", "?")
    in3 = pin_map.get("IN3", "?")
    in4 = pin_map.get("IN4", "?")
    return {
        "lang": "cpp",
        "code": f"""#include <Stepper.h>
const int stepPerRev = 2048;  // 28BYJ-48
Stepper myStepper(stepPerRev, {in1}, {in3}, {in2}, {in4});

void setup() {{
  myStepper.setSpeed(10);  // 10 RPM
  Serial.begin(9600);
  Serial.println("Stepper Ready");
}}

void loop() {{
  Serial.println("CW 360");
  myStepper.step(stepPerRev);   // 正轉一圈
  delay(500);
  Serial.println("CCW 360");
  myStepper.step(-stepPerRev);  // 反轉一圈
  delay(500);
}}""",
    }

def _tc_motor(pin_map):
    ena = pin_map.get("ENA", "?")
    in1 = pin_map.get("IN1", "?")
    in2 = pin_map.get("IN2", "?")
    return {
        "lang": "cpp",
        "code": f"""#define ENA {ena}
#define IN1 {in1}
#define IN2 {in2}

void setup() {{
  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
}}
void loop() {{
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  analogWrite(ENA, 200);  // 正轉
  delay(2000);
  analogWrite(ENA, 0);    // 停止
  delay(1000);
}}""",
    }

def _tc_relay(pin_map):
    pin = pin_map.get("IN", "?")
    return {
        "lang": "cpp",
        "code": f"""#define RELAY_PIN {pin}

void setup() {{
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // Active-LOW: 初始關閉
}}
void loop() {{
  digitalWrite(RELAY_PIN, LOW);  delay(3000); // ON
  digitalWrite(RELAY_PIN, HIGH); delay(3000); // OFF
}}""",
    }

def _tc_pump(pin_map):
    relay_pin = pin_map.get("IN", "?")
    return {
        "lang": "cpp",
        "code": f"""// Pump 透過 Relay 控制（Relay.COM -> Pump.VCC）
#define RELAY_PIN {relay_pin}

void setup() {{ pinMode(RELAY_PIN, OUTPUT); digitalWrite(RELAY_PIN, HIGH); }}
void loop() {{
  digitalWrite(RELAY_PIN, LOW);  delay(2000); // 澆水 2 秒 (Active-LOW)
  digitalWrite(RELAY_PIN, HIGH); delay(5000); // 等待 5 秒
}}""",
    }

def _tc_oled(pin_map):
    sda = pin_map.get("SDA", "?")
    scl = pin_map.get("SCL", "?")
    return {
        "lang": "cpp",
        "code": f"""#include <Wire.h>
#include <Adafruit_SSD1306.h>
// SDA={sda}, SCL={scl}
Adafruit_SSD1306 display(128, 64, &Wire, -1);

void setup() {{
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(0, 20);
  display.println("Hello!");
  display.display();
}}
void loop() {{}}""",
    }

def _tc_lcd(pin_map):
    sda = pin_map.get("SDA", "?")
    scl = pin_map.get("SCL", "?")
    return {
        "lang": "cpp",
        "code": f"""#include <Wire.h>
#include <LiquidCrystal_I2C.h>
// SDA={sda}, SCL={scl}
LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {{
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Hello STEM!");
}}
void loop() {{}}""",
    }

def _tc_speaker(pin_map):
    tx = pin_map.get("TX", "?")
    rx = pin_map.get("RX", "?")
    return {
        "lang": "cpp",
        "code": f"""#include <SoftwareSerial.h>
SoftwareSerial dfSerial({rx}, {tx}); // RX={rx}, TX={tx}

void setup() {{
  Serial.begin(9600);
  dfSerial.begin(9600);
  delay(500);
  // 播放第一首 (DFPlayer Mini 指令)
  byte cmd[] = {{0x7E,0xFF,0x06,0x03,0x00,0x00,0x01,0xEF}};
  dfSerial.write(cmd, 8);
  Serial.println("Playing track 1...");
}}
void loop() {{}}""",
    }


TEST_TEMPLATES: dict[str, callable] = {
    "NeoPixel": _tc_neopixel,
    "TempHumid": _tc_dht,
    "Ultrasonic": _tc_ultra,
    "PIR": _tc_pir,
    "Servo": _tc_servo,
    "LED_Single": _tc_led,
    "Buzzer_Active": _tc_buzzer,
    "Buzzer_Passive": _tc_buzzer,
    "SoilMoisture": _tc_soil,
    "Light": _tc_light,
    "LED_RGB": _tc_rgb,
    "Stepper": _tc_stepper,
    "DCMotor": _tc_motor,
    "Relay": _tc_relay,
    "Pump": _tc_pump,
    "OLED": _tc_oled,
    "LCD": _tc_lcd,
    "Speaker": _tc_speaker,
}
