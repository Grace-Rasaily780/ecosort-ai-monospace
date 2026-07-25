// Devkit standalone predictor: reads ESP32-CAM's serial JPEG stream (wired to
// GPIO16/17, hardware UART2), reassembles frames, POSTs each straight to the
// hosted thrashsort-api over plain WiFi/HTTP (hits the docker nginx on :8334
// directly, bypassing Caddy/TLS entirely to cut handshake latency), and
// drives the breadboard LEDs from the response. No PC in the loop anymore.
//
// Still relays the raw byte stream out over USB (Serial) so
// view_camera_feed.py / stream_camera_feed.py can be used optionally for
// debugging/viewing, and still accepts manual 'B'/'N'/'E' bytes from the USB
// serial monitor to test the LEDs directly.
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
// Requires the "ArduinoJson" library (Library Manager -> ArduinoJson, v6+).

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ---- WiFi (already configured on this network) ----
static const char *WIFI_SSID = "IIMS_HACKATHON 2026";
static const char *WIFI_PASSWORD = "google@123";

// ---- API ----
// Plain HTTP on port 80 (Caddy has an explicit http:// route for this host
// with no redirect-to-https) -- direct :8334 is firewalled externally, port
// 80 is open. Still no TLS handshake, just goes through Caddy instead of
// straight to nginx.
static const char *PREDICT_URL = "http://monospace.rootictech.com/predict";

#define RXD2 16
#define TXD2 17
#define BRIDGE_BAUD 115200

#define BIO_LED_GPIO 4
#define NONBIO_LED_GPIO 13
#define BLINK_MS 400

#define DETECT_INTERVAL_MS 2000
#define MAX_JUNK 60000
#define MAX_FRAME_BYTES 40000
#define MIN_FRAME_BYTES 3000  // real frames run ~9-10KB; smaller is a resync artifact

static const uint8_t SOI[2] = {0xFF, 0xD8};
static const uint8_t EOI[2] = {0xFF, 0xD9};

uint8_t *frameBuf;
size_t frameLen = 0;

unsigned long ledsOffAt = 0;
unsigned long lastPredictAt = 0;

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

int findSeq(const uint8_t *buf, size_t len, const uint8_t *seq, size_t from) {
  if (from + 2 > len) return -1;
  for (size_t i = from; i + 1 < len; i++) {
    if (buf[i] == seq[0] && buf[i + 1] == seq[1]) return (int)i;
  }
  return -1;
}

void runPredict(const uint8_t *jpeg, size_t len) {
  HTTPClient http;
  if (!http.begin(PREDICT_URL)) {
    Serial.println("http.begin failed");
    return;
  }

  const char *boundary = "thrashsortBoundary";
  String head = String("--") + boundary +
                "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\n"
                "Content-Type: image/jpeg\r\n\r\n";
  String tail = String("\r\n--") + boundary + "--\r\n";

  size_t bodyLen = head.length() + len + tail.length();
  uint8_t *body = (uint8_t *)malloc(bodyLen);
  if (!body) {
    Serial.println("OOM building request body");
    http.end();
    return;
  }
  memcpy(body, head.c_str(), head.length());
  memcpy(body + head.length(), jpeg, len);
  memcpy(body + head.length() + len, tail.c_str(), tail.length());

  http.addHeader("Content-Type", String("multipart/form-data; boundary=") + boundary);
  int status = http.POST(body, bodyLen);
  free(body);

  if (status != 200) {
    Serial.printf("predict request failed, status %d\n", status);
    http.end();
    return;
  }

  String resp = http.getString();
  http.end();

  StaticJsonDocument<2048> doc;
  DeserializationError err = deserializeJson(doc, resp);
  if (err) {
    Serial.printf("json parse failed: %s\n", err.c_str());
    return;
  }

  JsonArray detections = doc["detections"].as<JsonArray>();
  if (detections.size() == 0) {
    Serial.println("nothing detected");
    return;
  }

  const char *bestClass = nullptr;
  float bestConf = -1.0f;
  for (JsonObject d : detections) {
    float conf = d["confidence"];
    if (conf > bestConf) {
      bestConf = conf;
      bestClass = d["class_name"];
    }
  }

  Serial.printf("%s (%.2f)\n", bestClass, bestConf);
  if (strcmp(bestClass, "Bio-degradable") == 0) handleCommand('B');
  else if (strcmp(bestClass, "Non-Biodegradable") == 0) handleCommand('N');
  else if (strcmp(bestClass, "E-Waste") == 0) handleCommand('E');
}

void setup() {
  frameBuf = (uint8_t *)malloc(MAX_FRAME_BYTES);
  while (!frameBuf) delay(1000);  // OOM, halt

  pinMode(BIO_LED_GPIO, OUTPUT);
  pinMode(NONBIO_LED_GPIO, OUTPUT);
  setLeds(false, false);

  Serial.begin(BRIDGE_BAUD);
  Serial2.setRxBufferSize(32768);  // absorb CAM stream while blocked in runPredict()
  Serial2.begin(BRIDGE_BAUD, SERIAL_8N1, RXD2, TXD2);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.print("\nconnected, IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  while (Serial2.available()) {
    uint8_t b = Serial2.read();
    Serial.write(b);  // relay raw stream out USB, optional PC viewers

    if (frameLen < MAX_FRAME_BYTES) {
      frameBuf[frameLen++] = b;
    } else {
      frameLen = 0;  // overflow, drop and resync
    }
  }

  // manual override: 'B'/'N'/'E' typed into the USB serial monitor
  while (Serial.available()) {
    handleCommand(Serial.read());
  }

  int soi = findSeq(frameBuf, frameLen, SOI, 0);
  if (soi == -1) {
    if (frameLen > MAX_JUNK) frameLen = 0;
  } else {
    int eoi = findSeq(frameBuf, frameLen, EOI, soi + 2);
    if (eoi == -1) {
      if (soi > 0) {
        memmove(frameBuf, frameBuf + soi, frameLen - soi);
        frameLen -= soi;
      }
    } else {
      size_t jpegLen = eoi + 2 - soi;
      unsigned long now = millis();
      if (jpegLen >= MIN_FRAME_BYTES && now - lastPredictAt >= DETECT_INTERVAL_MS) {
        lastPredictAt = now;
        runPredict(frameBuf + soi, jpegLen);
      }
      memmove(frameBuf, frameBuf + eoi + 2, frameLen - (eoi + 2));
      frameLen -= (eoi + 2);
    }
  }

  if (ledsOffAt && millis() > ledsOffAt) {
    setLeds(false, false);
    ledsOffAt = 0;
  }
}
