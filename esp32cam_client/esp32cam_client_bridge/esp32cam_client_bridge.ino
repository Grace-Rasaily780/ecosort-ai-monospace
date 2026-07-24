// Devkit UART bridge: relays ESP32-CAM's serial JPEG stream (wired to
// GPIO16/17, hardware UART2) out over USB (Serial) so PC-side scripts
// (view_camera_feed.py / stream_camera_feed.py / test_live_predict.py) can
// read /dev/ttyUSB0. Also drives breadboard LEDs on this same devkit when a
// single-byte classification command comes back from the PC after a
// thrashsort-api /predict call — the devkit sees every PC->CAM byte anyway,
// so no CAM-side firmware involvement needed for this.
//
// Wiring: CAM GPIO14 -> devkit GPIO17 (TX2)
//         CAM GPIO15 -> devkit GPIO16 (RX2)
//         CAM 5V     -> devkit 5V
//         CAM GND    -> devkit GND
//
// Breadboard LEDs (this devkit):
//   GPIO4  = green = Bio-degradable
//   GPIO13 = red   = Non-BioDegradable
//   E-waste = both on
//
// Commands (single byte, from stream_camera_feed.py / test_live_predict.py):
//   'B' = Bio-degradable, 'N' = Non-BioDegradable, 'E' = E-waste

#define RXD2 16
#define TXD2 17
#define BRIDGE_BAUD 115200

#define BIO_LED_GPIO 4
#define NONBIO_LED_GPIO 13
#define BLINK_MS 400

unsigned long ledsOffAt = 0;

void setLeds(bool bio, bool nonBio) {
  digitalWrite(BIO_LED_GPIO, bio ? HIGH : LOW);
  digitalWrite(NONBIO_LED_GPIO, nonBio ? HIGH : LOW);
}

void handleCommand(uint8_t cmd) {
  switch (cmd) {
    case 'B': setLeds(true, false); break;
    case 'N': setLeds(false, true); break;
    case 'E': setLeds(true, true); break;
    default: return;
  }
  ledsOffAt = millis() + BLINK_MS;
}

void setup() {
  pinMode(BIO_LED_GPIO, OUTPUT);
  pinMode(NONBIO_LED_GPIO, OUTPUT);
  setLeds(false, false);

  Serial.begin(BRIDGE_BAUD);
  Serial2.begin(BRIDGE_BAUD, SERIAL_8N1, RXD2, TXD2);
}

void loop() {
  while (Serial2.available()) {
    Serial.write(Serial2.read());
  }
  while (Serial.available()) {
    uint8_t b = Serial.read();
    handleCommand(b);
    Serial2.write(b);
  }

  if (ledsOffAt && millis() > ledsOffAt) {
    setLeds(false, false);
    ledsOffAt = 0;
  }
}
