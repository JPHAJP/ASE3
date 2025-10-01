/*
  ESP32 Bluetooth Classic (SPP) LED control + print BT MAC
*/

#include "BluetoothSerial.h"
#include "esp_bt_device.h"   // <-- add this

#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled! Enable it in menuconfig or use a board with BT.
#endif

BluetoothSerial BT;

const int LED_PIN = 2;  // adjust if your board's LED is on another GPIO

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  delay(200);

  if (!BT.begin("ESP32_LED_BT")) {   // Device name
    Serial.println("BT init failed. Rebooting...");
    delay(1000);
    ESP.restart();
  }

  // --- Print Bluetooth MAC address
  const uint8_t* mac = esp_bt_dev_get_address();
  if (mac) {
    char macStr[18];
    sprintf(macStr, "%02X:%02X:%02X:%02X:%02X:%02X",
            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    Serial.print("Bluetooth device ready. MAC: ");
    Serial.println(macStr);
    BT.print("Hello from ESP32. MAC: "); BT.println(macStr);
  } else {
    Serial.println("Could not read BT MAC.");
  }

  Serial.println("Send '1' to turn ON, '0' to turn OFF (over Bluetooth).");
}

void loop() {
  if (BT.available()) {
    int b = BT.read();
    if (b == '1') {
      digitalWrite(LED_PIN, HIGH);
      BT.println("LED: ON");
      Serial.println("BT -> LED: ON");
    } else if (b == '0') {
      digitalWrite(LED_PIN, LOW);
      BT.println("LED: OFF");
      Serial.println("BT -> LED: OFF");
    } else if (b != '\r' && b != '\n') {
      BT.print("Echo: "); BT.write(b); BT.println();
      Serial.print("BT Echo: "); Serial.write(b); Serial.println();
    }
  }

  // (optional) mirror USB serial to BT
  if (Serial.available()) {
    BT.write(Serial.read());
  }
}
