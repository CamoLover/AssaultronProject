/*
  Assaultron Hardware Interface - Arduino Sketch Template
  This sketch connects to the Python hardware server via WiFi/Serial
*/

#include <WiFi.h>  // For ESP32, use <ESP8266WiFi.h> for ESP8266

// Network Configuration
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* server_ip = "192.168.1.100";  // Your computer's IP
const int server_port = 9999;

// Hardware Pins
const int LED_PIN = 2;
const int LEFT_SERVO_PIN = 18;
const int RIGHT_SERVO_PIN = 19;

// Libraries
#include <Servo.h>
Servo leftHand;
Servo rightHand;

WiFiClient client;

void setup() {
  Serial.begin(115200);
  
  // Initialize hardware
  pinMode(LED_PIN, OUTPUT);
  leftHand.attach(LEFT_SERVO_PIN);
  rightHand.attach(RIGHT_SERVO_PIN);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("WiFi connected!");
  
  // Connect to hardware server
  connectToServer();
}

void loop() {
  if (!client.connected()) {
    connectToServer();
  }
  
  // Check for commands from server
  if (client.available()) {
    String command = client.readStringUntil('\n');
    processCommand(command);
  }
  
  delay(100);
}

void connectToServer() {
  Serial.println("Connecting to hardware server...");
  if (client.connect(server_ip, server_port)) {
    Serial.println("Connected to hardware server!");
    // Register with server
    client.println("{\"type\": \"register\", \"device\": \"arduino\"}");
  } else {
    Serial.println("Connection failed, retrying in 5 seconds...");
    delay(5000);
  }
}

void processCommand(String jsonCommand) {
  // Parse JSON command and control hardware
  // Example: {"led": 75, "left_hand": 50, "right_hand": 100}
  
  Serial.println("Received: " + jsonCommand);
  
  // TODO: Implement JSON parsing and hardware control
  // For now, simple example:
  if (jsonCommand.indexOf("led") > -1) {
    // Extract LED value and set brightness
    analogWrite(LED_PIN, 255); // Full brightness example
  }
  
  // Send acknowledgment
  client.println("{\"status\": \"ok\", \"message\": \"Command executed\"}");
}