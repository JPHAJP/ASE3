/*
  ESP32 Bluetooth Gripper Controller
  
  Este código debe ejecutarse en el ESP32 para recibir comandos de control
  del gripper via Bluetooth desde la aplicación web.
  
  Funcionalidades:
  - Recibe comandos JSON con fuerza y posición del gripper
  - Controla servo motor para apertura/cierre
  - Control PWM para fuerza del gripper
  - Respuestas de confirmación
  
  Hardware requerido:
  - ESP32 (cualquier modelo con Bluetooth)
  - Servo motor (para apertura/cierre)
  - Motor DC o actuador lineal (para fuerza)
  - Driver de motor (L298N o similar)
  - Sensor de posición (potenciómetro o encoder - opcional)
  - Sensor de fuerza (celda de carga - opcional)
*/

#include "BluetoothSerial.h"
#include <ESP32Servo.h>
#include <ArduinoJson.h>

// Verificar si Bluetooth está disponible
#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled! Please run `make menuconfig` to enable it
#endif

// Configuración de pines
const int SERVO_PIN = 18;           // Pin del servo para apertura/cierre
const int MOTOR_PWM_PIN = 19;       // Pin PWM para control de fuerza
const int MOTOR_DIR_PIN1 = 21;      // Pin de dirección 1 del motor
const int MOTOR_DIR_PIN2 = 22;      // Pin de dirección 2 del motor
const int POSITION_SENSOR_PIN = 34; // Pin del sensor de posición (ADC)
const int FORCE_SENSOR_PIN = 35;    // Pin del sensor de fuerza (ADC)
const int LED_PIN = 2;              // LED integrado para status

// Configuración PWM
const int PWM_CHANNEL = 0;
const int PWM_FREQ = 1000;    // 1kHz
const int PWM_RESOLUTION = 8; // 8 bits (0-255)

// Variables globales
BluetoothSerial SerialBT;
Servo gripperServo;

// Estado del gripper
struct GripperState {
  float targetForce = 0.0;      // Fuerza objetivo (0-10N)
  float targetPosition = 0.0;   // Posición objetivo (0-100%)
  float currentForce = 0.0;     // Fuerza actual medida
  float currentPosition = 0.0;  // Posición actual medida
  bool isMoving = false;        // Estado de movimiento
  unsigned long lastCommandTime = 0;
} gripper;

// Configuración del sistema
struct Config {
  const char* deviceName = "ESP32_Gripper";
  const int servoMin = 0;      // Posición mínima del servo (cerrado)
  const int servoMax = 180;    // Posición máxima del servo (abierto)
  const int forceMin = 0;      // Fuerza mínima PWM
  const int forceMax = 255;    // Fuerza máxima PWM
  const float maxForce = 10.0; // Fuerza máxima en Newtons
  const unsigned long commandTimeout = 5000; // 5 segundos timeout
} config;

void setup() {
  Serial.begin(115200);
  
  // Configurar pines
  pinMode(LED_PIN, OUTPUT);
  pinMode(MOTOR_DIR_PIN1, OUTPUT);
  pinMode(MOTOR_DIR_PIN2, OUTPUT);
  pinMode(POSITION_SENSOR_PIN, INPUT);
  pinMode(FORCE_SENSOR_PIN, INPUT);
  
  // Configurar PWM
  ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(MOTOR_PWM_PIN, PWM_CHANNEL);
  
  // Configurar servo
  gripperServo.attach(SERVO_PIN);
  gripperServo.write(config.servoMin); // Posición inicial cerrada
  
  // Inicializar Bluetooth
  SerialBT.begin(config.deviceName);
  Serial.println("ESP32 Gripper Controller iniciado");
  Serial.println("Esperando conexiones Bluetooth...");
  
  // LED de inicio
  blinkLED(3, 200);
  
  // Estado inicial
  gripper.currentPosition = 0.0;
  gripper.targetPosition = 0.0;
  gripper.currentForce = 0.0;
  gripper.targetForce = 0.0;
  
  Serial.println("Sistema listo para recibir comandos");
}

void loop() {
  // Procesar comandos Bluetooth
  if (SerialBT.available()) {
    String command = SerialBT.readStringUntil('\n');
    command.trim();
    
    if (command.length() > 0) {
      processCommand(command);
    }
  }
  
  // Actualizar control del gripper
  updateGripperControl();
  
  // Leer sensores y actualizar estado
  updateSensorReadings();
  
  // Verificar timeout de comandos
  checkCommandTimeout();
  
  // Actualizar LED de estado
  updateStatusLED();
  
  delay(10); // Pequeño delay para estabilidad
}

void processCommand(String command) {
  Serial.println("Comando recibido: " + command);
  
  // Actualizar timestamp del último comando
  gripper.lastCommandTime = millis();
  
  // Procesar comandos especiales
  if (command.equals("INIT")) {
    handleInitCommand();
    return;
  }
  
  if (command.equals("TEST") || command.equals("PING")) {
    SerialBT.println("OK - ESP32 Gripper Ready");
    Serial.println("Test/Ping respondido");
    return;
  }
  
  if (command.equals("STATUS")) {
    sendStatusReport();
    return;
  }
  
  if (command.equals("EMERGENCY_STOP")) {
    handleEmergencyStop();
    return;
  }
  
  if (command.equals("DISCONNECT")) {
    handleDisconnect();
    return;
  }
  
  // Procesar comando simple formato: GRIP:force:position
  if (command.startsWith("GRIP:")) {
    processSimpleGripCommand(command);
    return;
  }
  
  // Procesar comando JSON
  if (command.startsWith("{")) {
    processJSONCommand(command);
    return;
  }
  
  // Comando no reconocido
  SerialBT.println("ERROR: Unknown command");
  Serial.println("Comando no reconocido: " + command);
}

void handleInitCommand() {
  Serial.println("Comando INIT - Inicializando gripper");
  
  // Resetear a posición inicial
  gripper.targetPosition = 0.0;
  gripper.targetForce = 0.0;
  gripper.isMoving = false;
  
  // Mover servo a posición inicial
  gripperServo.write(config.servoMin);
  
  // Detener motor
  stopMotor();
  
  SerialBT.println("INIT_OK - Gripper initialized");
  Serial.println("Gripper inicializado correctamente");
}

void processSimpleGripCommand(String command) {
  // Formato: GRIP:force:position
  int firstColon = command.indexOf(':', 5);
  int secondColon = command.indexOf(':', firstColon + 1);
  
  if (firstColon == -1 || secondColon == -1) {
    SerialBT.println("ERROR: Invalid GRIP command format");
    return;
  }
  
  float force = command.substring(5, firstColon).toFloat();
  float position = command.substring(firstColon + 1, secondColon).toFloat();
  
  // Validar rangos
  force = constrain(force, 0.0, config.maxForce);
  position = constrain(position, 0.0, 100.0);
  
  // Aplicar comando
  setGripperTarget(force, position);
  
  String response = "GRIP_OK:F=" + String(force, 2) + ":P=" + String(position, 1);
  SerialBT.println(response);
  
  Serial.println("Comando simple procesado - F:" + String(force) + " P:" + String(position));
}

void processJSONCommand(String command) {
  // Crear buffer para JSON
  StaticJsonDocument<200> doc;
  
  // Parsear JSON
  DeserializationError error = deserializeJson(doc, command);
  
  if (error) {
    SerialBT.println("ERROR: Invalid JSON format");
    Serial.println("Error parseando JSON: " + String(error.c_str()));
    return;
  }
  
  // Verificar tipo de comando
  if (!doc.containsKey("type")) {
    SerialBT.println("ERROR: Missing command type");
    return;
  }
  
  String type = doc["type"].as<String>();
  
  if (type.equals("gripper_control")) {
    float force = doc["force"] | 0.0;
    float position = doc["position"] | 0.0;
    
    // Validar rangos
    force = constrain(force, 0.0, config.maxForce);
    position = constrain(position, 0.0, 100.0);
    
    // Aplicar comando
    setGripperTarget(force, position);
    
    // Responder con JSON
    StaticJsonDocument<150> response;
    response["status"] = "OK";
    response["force"] = force;
    response["position"] = position;
    response["timestamp"] = millis();
    
    String responseStr;
    serializeJson(response, responseStr);
    SerialBT.println(responseStr);
    
    Serial.println("Comando JSON procesado - F:" + String(force) + " P:" + String(position));
  }
  else {
    SerialBT.println("ERROR: Unknown command type");
  }
}

void setGripperTarget(float force, float position) {
  gripper.targetForce = force;
  gripper.targetPosition = position;
  gripper.isMoving = true;
  gripper.lastCommandTime = millis();
  
  Serial.println("Nuevo objetivo - Fuerza: " + String(force) + "N, Posición: " + String(position) + "%");
}

void updateGripperControl() {
  if (!gripper.isMoving) return;
  
  // Control de posición (servo)
  updatePositionControl();
  
  // Control de fuerza (motor PWM)
  updateForceControl();
  
  // Verificar si llegamos al objetivo
  float positionError = abs(gripper.currentPosition - gripper.targetPosition);
  float forceError = abs(gripper.currentForce - gripper.targetForce);
  
  if (positionError < 2.0 && forceError < 0.5) {
    gripper.isMoving = false;
    Serial.println("Objetivo alcanzado");
  }
}

void updatePositionControl() {
  // Mapear posición porcentual a ángulo del servo
  int servoAngle = map(gripper.targetPosition, 0, 100, config.servoMin, config.servoMax);
  
  // Mover servo gradualmente para suavidad
  int currentAngle = gripperServo.read();
  int targetAngle = servoAngle;
  
  if (abs(currentAngle - targetAngle) > 2) {
    int step = (targetAngle > currentAngle) ? 2 : -2;
    int newAngle = constrain(currentAngle + step, config.servoMin, config.servoMax);
    gripperServo.write(newAngle);
  }
}

void updateForceControl() {
  // Mapear fuerza a PWM
  int pwmValue = map(gripper.targetForce * 100, 0, config.maxForce * 100, 
                     config.forceMin, config.forceMax);
  
  // Aplicar PWM al motor
  if (pwmValue > 10) { // Umbral mínimo para evitar ruido
    // Dirección del motor (ajustar según hardware)
    digitalWrite(MOTOR_DIR_PIN1, HIGH);
    digitalWrite(MOTOR_DIR_PIN2, LOW);
    ledcWrite(PWM_CHANNEL, pwmValue);
  } else {
    stopMotor();
  }
}

void updateSensorReadings() {
  // Leer sensor de posición (potenciómetro en servo)
  int posRaw = analogRead(POSITION_SENSOR_PIN);
  gripper.currentPosition = map(posRaw, 0, 4095, 0, 100);
  
  // Leer sensor de fuerza (celda de carga)
  int forceRaw = analogRead(FORCE_SENSOR_PIN);
  gripper.currentForce = map(forceRaw, 0, 4095, 0, config.maxForce * 100) / 100.0;
  
  // Filtrar lecturas para estabilidad
  static float posFilter = 0;
  static float forceFilter = 0;
  
  posFilter = posFilter * 0.8 + gripper.currentPosition * 0.2;
  forceFilter = forceFilter * 0.8 + gripper.currentForce * 0.2;
  
  gripper.currentPosition = posFilter;
  gripper.currentForce = forceFilter;
}

void stopMotor() {
  digitalWrite(MOTOR_DIR_PIN1, LOW);
  digitalWrite(MOTOR_DIR_PIN2, LOW);
  ledcWrite(PWM_CHANNEL, 0);
}

void handleEmergencyStop() {
  Serial.println("PARADA DE EMERGENCIA ACTIVADA");
  
  // Detener todo inmediatamente
  stopMotor();
  gripper.isMoving = false;
  gripper.targetForce = 0.0;
  
  // No cambiar posición del servo para mantener agarre
  
  SerialBT.println("EMERGENCY_STOP_OK");
  
  // LED de emergencia
  for (int i = 0; i < 10; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
    delay(50);
  }
}

void handleDisconnect() {
  Serial.println("Comando de desconexión recibido");
  
  // Mover a posición segura
  gripper.targetPosition = 0.0;
  gripper.targetForce = 0.0;
  gripperServo.write(config.servoMin);
  stopMotor();
  
  SerialBT.println("DISCONNECT_OK - Gripper safe mode");
  
  delay(100);
  // Nota: No cerramos SerialBT para permitir reconexión
}

void sendStatusReport() {
  StaticJsonDocument<300> status;
  
  status["device"] = config.deviceName;
  status["uptime"] = millis();
  status["force"]["current"] = gripper.currentForce;
  status["force"]["target"] = gripper.targetForce;
  status["position"]["current"] = gripper.currentPosition;
  status["position"]["target"] = gripper.targetPosition;
  status["isMoving"] = gripper.isMoving;
  status["lastCommand"] = gripper.lastCommandTime;
  
  String statusStr;
  serializeJson(status, statusStr);
  SerialBT.println(statusStr);
  
  Serial.println("Status report enviado");
}

void checkCommandTimeout() {
  unsigned long currentTime = millis();
  
  if (gripper.lastCommandTime > 0 && 
      (currentTime - gripper.lastCommandTime > config.commandTimeout)) {
    
    // Timeout - mover a posición segura
    if (gripper.isMoving) {
      Serial.println("Timeout de comando - modo seguro");
      gripper.targetForce = 0.0;
      stopMotor();
      gripper.isMoving = false;
    }
  }
}

void updateStatusLED() {
  static unsigned long lastBlink = 0;
  static bool ledState = false;
  unsigned long currentTime = millis();
  
  if (gripper.isMoving) {
    // Parpadeo rápido cuando se mueve
    if (currentTime - lastBlink > 100) {
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState);
      lastBlink = currentTime;
    }
  } else if (SerialBT.hasClient()) {
    // Encendido fijo cuando conectado pero inmóvil
    digitalWrite(LED_PIN, HIGH);
  } else {
    // Parpadeo lento cuando desconectado
    if (currentTime - lastBlink > 1000) {
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState);
      lastBlink = currentTime;
    }
  }
}

void blinkLED(int times, int delayMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(delayMs);
    digitalWrite(LED_PIN, LOW);
    delay(delayMs);
  }
}

// Función de debug para monitor serie
void printDebugInfo() {
  static unsigned long lastDebug = 0;
  
  if (millis() - lastDebug > 2000) { // Cada 2 segundos
    Serial.println("=== DEBUG GRIPPER ===");
    Serial.println("Posición: " + String(gripper.currentPosition) + "% (objetivo: " + String(gripper.targetPosition) + "%)");
    Serial.println("Fuerza: " + String(gripper.currentForce) + "N (objetivo: " + String(gripper.targetForce) + "N)");
    Serial.println("Moviendo: " + String(gripper.isMoving ? "SÍ" : "NO"));
    Serial.println("BT Conectado: " + String(SerialBT.hasClient() ? "SÍ" : "NO"));
    Serial.println("=====================");
    lastDebug = millis();
  }
}