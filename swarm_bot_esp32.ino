/*
  SWARM BOT — ESP32 Firmware
  ---------------------------
  Responsibilities:
    - Connect to WiFi
    - Run HTTP server, accept /forward /backward /left /right /stop
    - Drive TB6612FNG motor driver at FIXED SPEED = 90
    - SAFETY: if no command received within COMMAND_TIMEOUT ms, auto STOP

  Wiring (as per project spec):
    TB6612FNG STBY -> GPIO 25
    TB6612FNG PWMA -> GPIO 26   (Left motor speed)
    TB6612FNG AIN1 -> GPIO 27   (Left motor dir 1)
    TB6612FNG AIN2 -> GPIO 14   (Left motor dir 2)
    TB6612FNG PWMB -> GPIO 16   (Right motor speed)
    TB6612FNG BIN1 -> GPIO 32   (Right motor dir 1)
    TB6612FNG BIN2 -> GPIO 13   (Right motor dir 2)

    A01/A02 -> LEFT motor
    B01/B02 -> RIGHT motor

    Common GND between ESP32, TB6612FNG, and motor battery.
    Do NOT power ESP32 from the motor battery/supply.
*/

#include <WiFi.h>
#include <WebServer.h>

// ---------------- WiFi credentials ----------------
const char* ssid     = "A5x_Industries";
const char* password = "a5x@1234";

// ---------------- Motor pins ----------------
#define STBY 25

#define PWMA 26
#define AIN1 27
#define AIN2 14

#define PWMB 16
#define BIN1 32
#define BIN2 13

// ---------------- PWM (LEDC) config ----------------
const int PWM_FREQ       = 5000;
const int PWM_RESOLUTION = 8;      // 0-255
const int CH_A = 0;
const int CH_B = 1;

// ---------------- MOTOR SPEEDS ----------------
// Separate speeds for forward/backward vs turning.
// Lower turn speed = slower, more controlled rotation = more stable ArUco tracking.
// Tune these values if needed (range: 0-255, PWM duty cycle):
int forwardSpeed = 120;     // Speed for FORWARD and BACKWARD
int turnSpeed = 60;         // Speed for LEFT and RIGHT (slower for stability)

// ---------------- Safety timeout ----------------
const unsigned long COMMAND_TIMEOUT = 1000;  // ms; auto-stop if no command received
unsigned long lastCommandTime = 0;
bool isStopped = true;

WebServer server(80);

// ---------------- Low-level motor helpers ----------------
void stopMotors() {
  digitalWrite(AIN1, LOW);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, LOW);
  digitalWrite(BIN2, LOW);
  ledcWrite(CH_A, 0);
  ledcWrite(CH_B, 0);
  isStopped = true;
}

void moveForward() {
  digitalWrite(AIN1, HIGH);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, HIGH);
  digitalWrite(BIN2, LOW);
  ledcWrite(CH_A, forwardSpeed);
  ledcWrite(CH_B, forwardSpeed);
  isStopped = false;
}

void moveBackward() {
  digitalWrite(AIN1, LOW);
  digitalWrite(AIN2, HIGH);
  digitalWrite(BIN1, LOW);
  digitalWrite(BIN2, HIGH);
  ledcWrite(CH_A, forwardSpeed);
  ledcWrite(CH_B, forwardSpeed);
  isStopped = false;
}

// Left motor reverse + Right motor forward -> turn LEFT
void turnLeft() {
  digitalWrite(AIN1, LOW);
  digitalWrite(AIN2, HIGH);
  digitalWrite(BIN1, HIGH);
  digitalWrite(BIN2, LOW);
  ledcWrite(CH_A, turnSpeed);
  ledcWrite(CH_B, turnSpeed);
  isStopped = false;
}

// Left motor forward + Right motor reverse -> turn RIGHT
void turnRight() {
  digitalWrite(AIN1, HIGH);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, LOW);
  digitalWrite(BIN2, HIGH);
  ledcWrite(CH_A, turnSpeed);
  ledcWrite(CH_B, turnSpeed);
  isStopped = false;
}

// ---------------- HTTP handlers ----------------
void handleForward() {
  moveForward();
  lastCommandTime = millis();
  server.send(200, "text/plain", "OK forward");
}

void handleBackward() {
  moveBackward();
  lastCommandTime = millis();
  server.send(200, "text/plain", "OK backward");
}

void handleLeft() {
  turnLeft();
  lastCommandTime = millis();
  server.send(200, "text/plain", "OK left");
}

void handleRight() {
  turnRight();
  lastCommandTime = millis();
  server.send(200, "text/plain", "OK right");
}

void handleStop() {
  stopMotors();
  lastCommandTime = millis();
  server.send(200, "text/plain", "OK stop");
}

void handleRoot() {
  String msg = "SWARM BOT ESP32 ready. Forward speed: ";
  msg += String(forwardSpeed);
  msg += ", Turn speed: ";
  msg += String(turnSpeed);
  server.send(200, "text/plain", msg);
}

// ---------------- Setup ----------------
void setup() {
  Serial.begin(115200);

  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);
  pinMode(STBY, OUTPUT);

  digitalWrite(STBY, HIGH);  // enable TB6612FNG

  ledcSetup(CH_A, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PWMA, CH_A);

  ledcSetup(CH_B, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PWMB, CH_B);

  stopMotors();

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected! ESP32 IP address: ");
  Serial.println(WiFi.localIP());   // <-- use this in laptop config.py

  server.on("/", handleRoot);
  server.on("/forward", handleForward);
  server.on("/backward", handleBackward);
  server.on("/left", handleLeft);
  server.on("/right", handleRight);
  server.on("/stop", handleStop);

  server.begin();
  Serial.println("HTTP server started");

  lastCommandTime = millis();
}

// ---------------- Main loop ----------------
void loop() {
  server.handleClient();

  // SAFETY: auto-stop if no command received within COMMAND_TIMEOUT
  if (!isStopped && (millis() - lastCommandTime > COMMAND_TIMEOUT)) {
    stopMotors();
    Serial.println("Safety timeout - no command received, motors stopped.");
  }
}
