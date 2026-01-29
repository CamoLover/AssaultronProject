"""
Vision System for Assaultron - Perception Layer (MediaPipe Version)

This module provides webcam-based vision capabilities using MediaPipe 
EfficientDet-Lite0 for fast CPU-based object detection.

It integrates with the embodied agent architecture by feeding detected 
entities into the WorldState.
"""

import cv2
import base64
import threading
import time
import os
import requests
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import numpy as np

# Import MediaPipe
try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("[VISION WARNING] mediapipe not installed. Run: pip install mediapipe")


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class DetectedEntity:
    """Represents a single detected object/person"""
    entity_id: str          # Unique identifier (e.g., "person_1")
    class_name: str         # Class name (person, cup, chair, etc.)
    confidence: float       # Confidence 0.0-1.0
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    center: Tuple[int, int]
    area_percent: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": self.bbox,
            "center": self.center,
            "area_percent": round(self.area_percent, 2)
        }


@dataclass
class VisionState:
    """Current state of what the vision system sees"""
    enabled: bool = False
    camera_active: bool = False
    camera_id: int = 0
    available_cameras: List[Dict[str, Any]] = field(default_factory=list)
    
    entities: List[DetectedEntity] = field(default_factory=list)
    person_count: int = 0
    object_count: int = 0
    
    scene_description: str = "No visual input"
    threat_assessment: str = "none"
    
    fps: float = 0.0
    processing_time_ms: float = 0.0
    
    current_frame_b64: str = ""
    frame_width: int = 640
    frame_height: int = 480
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "camera_active": self.camera_active,
            "camera_id": self.camera_id,
            "available_cameras": self.available_cameras,
            "entities": [e.to_dict() for e in self.entities],
            "person_count": self.person_count,
            "object_count": self.object_count,
            "scene_description": self.scene_description,
            "threat_assessment": self.threat_assessment,
            "fps": round(self.fps, 1),
            "processing_time_ms": round(self.processing_time_ms, 1),
            "frame_width": self.frame_width,
            "frame_height": self.frame_height
        }


# ============================================================================
# VISION SYSTEM
# ============================================================================

class VisionSystem:
    """
    Main vision system using MediaPipe Object Detector.
    Lightweight and fast CPU inference.
    """
    
    MODEL_URL = "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite"
    MODEL_FILENAME = "efficientdet_lite0.tflite"
    
    # Priority classes for AI attention
    PRIORITY_CLASSES = {
        "person": 10,
        "cat": 5, "dog": 5, "bird": 4,
        "cell phone": 3, "laptop": 3, "tv": 3,
        "bottle": 2, "cup": 2, "book": 2
    }
    
    # Classes causing threat alerts
    ALERT_CLASSES = ["knife", "scissors", "gun", "baseball bat"]

    def __init__(self, logger=None):
        self.logger = logger
        self.detector = None
        
        self.state = VisionState()
        self._lock = threading.Lock()
        
        # Capture
        self._capture = None
        self._capture_thread = None
        self._running = False
        
        self.detection_confidence = 0.5
        self.detection_interval = 0.1  # Limit to 10 detections/sec to save CPU
        self._last_detection_time = 0.0
        self._frame_times: List[float] = []
        
        # Ensure model exists
        self._ensure_model_downloaded()
        
        self._log("Vision System initialized (MediaPipe)")

    def _log(self, message: str, level: str = "VISION"):
        if self.logger and hasattr(self.logger, 'log_event'):
            self.logger.log_event(message, level)
        else:
            print(f"[{level}] {message}")

    def _ensure_model_downloaded(self):
        """Download efficientdet model if missing"""
        if not os.path.exists(self.MODEL_FILENAME):
            self._log(f"Downloading MediaPipe model ({self.MODEL_FILENAME})...")
            try:
                response = requests.get(self.MODEL_URL)
                with open(self.MODEL_FILENAME, 'wb') as f:
                    f.write(response.content)
                self._log("Model download complete.")
            except Exception as e:
                self._log(f"Failed to download detection model: {e}", "ERROR")

    def _init_detector(self) -> bool:
        """Initialize MediaPipe Object Detector"""
        if not MEDIAPIPE_AVAILABLE:
            return False
            
        if self.detector is not None:
            return True
            
        try:
            if not os.path.exists(self.MODEL_FILENAME):
                self._ensure_model_downloaded()
                
            base_options = python.BaseOptions(model_asset_path=self.MODEL_FILENAME)
            options = vision.ObjectDetectorOptions(
                base_options=base_options,
                score_threshold=self.detection_confidence,
                max_results=10,
                running_mode=vision.RunningMode.IMAGE
            )
            self.detector = vision.ObjectDetector.create_from_options(options)
            self._log("MediaPipe Object Detector loaded")
            return True
        except Exception as e:
            self._log(f"Failed to load detector: {e}", "ERROR")
            return False

    # ========================================================================
    # CAMERA & CAPTURE
    # ========================================================================
    
    def enumerate_cameras(self, max_cameras: int = 5) -> List[Dict[str, Any]]:
        cameras = []
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cameras.append({"id": i, "name": f"Camera {i}", "resolution": f"{w}x{h}"})
                cap.release()
        
        with self._lock:
            self.state.available_cameras = cameras
        return cameras
    
    def select_camera(self, camera_id: int) -> bool:
        if self._running:
            self.stop_capture()
        with self._lock:
            self.state.camera_id = camera_id
        return True
    
    def start_capture(self) -> bool:
        if self._running: return True
        if not self._init_detector(): return False
        
        self._capture = cv2.VideoCapture(self.state.camera_id, cv2.CAP_DSHOW)
        if not self._capture.isOpened():
            self._log(f"Failed to open camera {self.state.camera_id}", "ERROR")
            return False
            
        # Optimize for speed
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._capture.set(cv2.CAP_PROP_FPS, 30)
        
        with self._lock:
            self.state.enabled = True
            self.state.camera_active = True
            
        self._running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        
        self._log(f"Vision capture started on camera {self.state.camera_id}")
        return True
        
    def stop_capture(self) -> bool:
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=1.0)
            self._capture_thread = None
            
        if self._capture:
            self._capture.release()
            self._capture = None
            
        with self._lock:
            self.state.enabled = False
            self.state.camera_active = False
            self.state.scene_description = "Vision disabled"
            
        self._log("Vision capture stopped")
        return True

    def toggle_capture(self) -> bool:
        if self._running:
            self.stop_capture()
            return False
        else:
            return self.start_capture()
            
    # ========================================================================
    # MAIN LOOP
    # ========================================================================
    
    def _capture_loop(self):
        while self._running and self._capture:
            loop_start = time.time()
            
            ret, frame = self._capture.read()
            if not ret:
                time.sleep(0.01)
                continue
                
            # Perform detection at interval
            if time.time() - self._last_detection_time >= self.detection_interval:
                self._last_detection_time = time.time()
                det_start = time.time()
                
                # Convert for MediaPipe (BGR -> RGB)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                
                # Run Detection
                detection_result = self.detector.detect(mp_image)
                
                # Process Results
                entities = self._process_detections(detection_result, frame.shape)
                
                # Draw boxes
                frame = self._draw_detections(frame, entities)
                
                # Analyze scene
                desc = self._generate_scene_description(entities)
                threat = self._assess_threat(entities)
                
                proc_time = (time.time() - det_start) * 1000
                
                with self._lock:
                    self.state.entities = entities
                    self.state.person_count = sum(1 for e in entities if e.class_name == "person")
                    self.state.object_count = len(entities) - self.state.person_count
                    self.state.scene_description = desc
                    self.state.threat_assessment = threat
                    self.state.processing_time_ms = proc_time

            # Update FPS
            self._frame_times.append(time.time())
            if len(self._frame_times) > 30: self._frame_times.pop(0)
            fps = len(self._frame_times) / (self._frame_times[-1] - self._frame_times[0]) if len(self._frame_times) > 1 else 0
            
            # Encode frame
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            b64_frame = base64.b64encode(buffer).decode('utf-8')
            
            with self._lock:
                self.state.current_frame_b64 = b64_frame
                self.state.fps = fps
                
            # Cap FPS to 30
            elapsed = time.time() - loop_start
            if elapsed < 0.033:
                time.sleep(0.033 - elapsed)
                
    def _process_detections(self, result, shape) -> List[DetectedEntity]:
        """Convert MediaPipe results to DetectedEntity list"""
        h, w, _ = shape
        entities = []
        frame_area = w * h
        
        class_counts = {}
        
        for detection in result.detections:
            category = detection.categories[0]
            class_name = category.category_name
            score = category.score
            
            if score < self.detection_confidence:
                continue
                
            # Bounding box
            bbox = detection.bounding_box
            x1, y1 = int(bbox.origin_x), int(bbox.origin_y)
            x2, y2 = x1 + int(bbox.width), y1 + int(bbox.height)
            
            # Clamp
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            area_pct = ((x2 - x1) * (y2 - y1) / frame_area) * 100
            
            # ID generation
            if class_name not in class_counts: class_counts[class_name] = 0
            entity_id = f"{class_name}_{class_counts[class_name]}"
            class_counts[class_name] += 1
            
            entities.append(DetectedEntity(
                entity_id=entity_id,
                class_name=class_name,
                confidence=score,
                bbox=(x1, y1, x2, y2),
                center=(center_x, center_y),
                area_percent=area_pct
            ))
            
        entities.sort(key=lambda e: (-self.PRIORITY_CLASSES.get(e.class_name, 0), -e.confidence))
        return entities

    def _draw_detections(self, frame, entities):
        for e in entities:
            x1, y1, x2, y2 = e.bbox
            color = (0, 255, 0) if e.class_name == "person" else (255, 165, 0)
            if e.class_name in self.ALERT_CLASSES: color = (0, 0, 255)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{e.class_name} {e.confidence:.0%}"
            cv2.rectangle(frame, (x1, y1-20), (x1+150, y1), color, -1)
            cv2.putText(frame, label, (x1+5, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1)
        return frame

    def _generate_scene_description(self, entities):
        if not entities: return "No objects detected."
        
        counts = {}
        for e in entities: counts[e.class_name] = counts.get(e.class_name, 0) + 1
        
        parts = []
        if "person" in counts:
            num = counts.pop("person")
            person = next((e for e in entities if e.class_name == "person"), None)
            dist = "nearby" if person and person.area_percent > 10 else "visible"
            parts.append(f"{num} person(s) {dist}")
            
        for name, count in sorted(counts.items(), key=lambda x: -x[1]):
            parts.append(f"{count} {name}{'s' if count > 1 else ''}")
            
        return f"I see: {', '.join(parts)}"

    def _assess_threat(self, entities):
        for e in entities:
            if e.class_name in self.ALERT_CLASSES: return "high"
        
        people = [e for e in entities if e.class_name == "person"]
        if people:
            for p in people:
                if p.area_percent > 30: return "medium" # Too close
            return "low"
            
        return "none"

    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def get_state(self) -> VisionState:
        with self._lock:
            # Return copy to prevent race conditions
            return VisionState(
                enabled=self.state.enabled,
                camera_active=self.state.camera_active,
                camera_id=self.state.camera_id,
                available_cameras=list(self.state.available_cameras),
                entities=list(self.state.entities),
                person_count=self.state.person_count,
                object_count=self.state.object_count,
                scene_description=self.state.scene_description,
                threat_assessment=self.state.threat_assessment,
                fps=self.state.fps,
                processing_time_ms=self.state.processing_time_ms,
                current_frame_b64=self.state.current_frame_b64,
                frame_width=self.state.frame_width,
                frame_height=self.state.frame_height
            )

    def get_frame_b64(self) -> str:
        with self._lock: return self.state.current_frame_b64
        
    def get_entities_for_world_state(self) -> List[str]:
        with self._lock: return [e.entity_id for e in self.state.entities]
        
    def get_scene_for_cognitive_layer(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "scene_description": self.state.scene_description,
                "entities": [e.to_dict() for e in self.state.entities[:6]],
                "threat_level": self.state.threat_assessment
            }
            
    def set_detection_confidence(self, conf: float):
        self.detection_confidence = max(0.1, min(0.9, conf))
        if self.detector: 
            # Re-init detector with new threshold (limitation of MediaPipe options)
            # Actually simplest to just filter results for now
            pass
