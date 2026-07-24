// ESP32-CAM (AI-Thinker) firmware: captures JPEG frames and streams them out
// over UART2 (GPIO15 TX / GPIO14 RX) to the devkit bridge (esp32cam_client.ino
// on /dev/ttyUSB0). LED classification feedback is driven by the devkit
// itself (breadboard LEDs on its own GPIO13/GPIO4) since it already sees
// every command byte relayed from the PC — this board just streams frames.
//
// Replaces the previously-flashed unknown-source firmware. Written from
// scratch against the standard AI-Thinker pin map since no source for the
// original existed to patch.
//
// Wiring (unchanged): CAM GPIO14 (RX) -> devkit GPIO17 (TX2)
//                      CAM GPIO15 (TX) -> devkit GPIO16 (RX2)
//                      CAM 5V     -> devkit 5V
//                      CAM GND    -> devkit GND
//
#include "esp_camera.h"

#define CAM_TX 15
#define CAM_RX 14
#define BRIDGE_BAUD 115200

// Standard AI-Thinker ESP32-CAM pin map
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

HardwareSerial CamLink(2);

void setup() {
  CamLink.begin(BRIDGE_BAUD, SERIAL_8N1, CAM_RX, CAM_TX);

  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_DRAM;  // avoid depending on PSRAM being enabled/present

  if (esp_camera_init(&config) != ESP_OK) {
    while (true) delay(1000);
  }
}

void loop() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (fb) {
    CamLink.write(fb->buf, fb->len);
    esp_camera_fb_return(fb);
  }
}
