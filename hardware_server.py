#!/usr/bin/env python3
"""
Hardware Interface Server for Assaultron
This server handles hardware communication and can be extended for Arduino/ESP32 integration
"""

import socket
import json
import threading
import time
from datetime import datetime
import requests

class HardwareInterface:
    def __init__(self, main_server_url="http://127.0.0.1:8080"):
        self.main_server_url = main_server_url
        self.hardware_state = {
            "led_intensity": 50,
            "hands": {
                "left": {"position": 0, "status": "closed"},
                "right": {"position": 0, "status": "closed"}
            }
        }
        self.arduino_connected = False
        self.socket_server = None
        self.running = False
        
    def log(self, message, level="INFO"):
        """Log events with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def start_socket_server(self, port=9999):
        """Start socket server for hardware communication"""
        try:
            self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_server.bind(('127.0.0.1', port))
            self.socket_server.listen(5)
            self.running = True
            
            self.log(f"Hardware interface listening on port {port}")
            
            while self.running:
                try:
                    client, addr = self.socket_server.accept()
                    self.log(f"Hardware client connected: {addr}")
                    threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()
                except Exception as e:
                    if self.running:
                        self.log(f"Socket error: {e}", "ERROR")
                        
        except Exception as e:
            self.log(f"Failed to start socket server: {e}", "ERROR")
    
    def handle_client(self, client):
        """Handle connected hardware client (Arduino/ESP32)"""
        try:
            while self.running:
                data = client.recv(1024).decode('utf-8')
                if not data:
                    break
                    
                self.log(f"Received from hardware: {data}")
                
                # Parse hardware commands
                try:
                    command = json.loads(data)
                    response = self.process_hardware_command(command)
                    client.send(json.dumps(response).encode('utf-8') + b'\n')
                except json.JSONDecodeError:
                    # Handle simple text commands
                    response = {"status": "error", "message": "Invalid JSON format"}
                    client.send(json.dumps(response).encode('utf-8') + b'\n')
                    
        except Exception as e:
            self.log(f"Client handler error: {e}", "ERROR")
        finally:
            client.close()
            self.log("Hardware client disconnected")
    
    def process_hardware_command(self, command):
        """Process commands from hardware"""
        cmd_type = command.get("type", "")
        
        if cmd_type == "status":
            return {
                "status": "ok",
                "hardware_state": self.hardware_state,
                "timestamp": datetime.now().isoformat()
            }
        elif cmd_type == "ping":
            return {"status": "ok", "message": "pong"}
        elif cmd_type == "register":
            self.arduino_connected = True
            self.log("Arduino/Hardware registered successfully")
            return {"status": "ok", "message": "Hardware registered"}
        else:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}
    
    def sync_with_main_server(self):
        """Periodically sync hardware state with main server"""
        while self.running:
            try:
                # Get current state from main server
                response = requests.get(f"{self.main_server_url}/api/hardware", timeout=5)
                if response.status_code == 200:
                    new_state = response.json()
                    
                    # Check if state changed
                    if new_state != self.hardware_state:
                        self.log("Hardware state updated from main server")
                        self.hardware_state = new_state
                        self.send_to_arduino()
                        
            except Exception as e:
                self.log(f"Sync error: {e}", "ERROR")
            
            time.sleep(2)  # Sync every 2 seconds
    
    def send_to_arduino(self):
        """Send current hardware state to connected Arduino"""
        if not self.arduino_connected:
            return
            
        # This would send commands to actual Arduino
        self.log(f"Sending to Arduino: LED={self.hardware_state['led_intensity']}%, " +
                f"Left={self.hardware_state['hands']['left']['position']}%, " +
                f"Right={self.hardware_state['hands']['right']['position']}%")
        
        # TODO: Implement actual Arduino communication
        # Example Arduino command format:
        # arduino_command = {
        #     "led": self.hardware_state["led_intensity"],
        #     "left_hand": self.hardware_state["hands"]["left"]["position"],
        #     "right_hand": self.hardware_state["hands"]["right"]["position"]
        # }
    
    def create_arduino_sketch_template(self):
        """Generate Arduino sketch template for integration"""
        sketch = '''
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
    String command = client.readStringUntil('\\n');
    processCommand(command);
  }
  
  delay(100);
}

void connectToServer() {
  Serial.println("Connecting to hardware server...");
  if (client.connect(server_ip, server_port)) {
    Serial.println("Connected to hardware server!");
    // Register with server
    client.println("{\\"type\\": \\"register\\", \\"device\\": \\"arduino\\"}");
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
  client.println("{\\"status\\": \\"ok\\", \\"message\\": \\"Command executed\\"}");
}
'''
        
        with open("arduino_template.ino", "w") as f:
            f.write(sketch.strip())
        self.log("Arduino sketch template created: arduino_template.ino")
    
    def stop(self):
        """Stop the hardware interface"""
        self.running = False
        if self.socket_server:
            self.socket_server.close()
        self.log("Hardware interface stopped")

def main():
    hardware = HardwareInterface()
    
    # Create Arduino template
    hardware.create_arduino_sketch_template()
    
    try:
        # Start sync thread
        sync_thread = threading.Thread(target=hardware.sync_with_main_server, daemon=True)
        sync_thread.start()
        
        # Start socket server (blocking)
        hardware.start_socket_server()
        
    except KeyboardInterrupt:
        hardware.log("Shutting down hardware interface...")
        hardware.stop()

if __name__ == "__main__":
    main()