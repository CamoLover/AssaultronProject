"""
Wake Word Manager - always-on hotword detection ("Hey Jarvis" by default).

Uses openWakeWord (ONNX runtime) to continuously listen on the microphone.
When the wake word is detected it:
  1. releases the microphone (so speech-to-text can use it),
  2. plays a short spoken acknowledgment ("Yes?" / "Oui?") via the supplied
     ``ack_player`` callback,
  3. fires the ``on_wake`` callback so the host can capture the actual command,
  4. stays paused while ``is_busy`` reports True, then resumes scanning.

The manager gracefully disables itself if openwakeword / pyaudio / numpy are
unavailable, mirroring the optional-dependency pattern used by the STT manager.
"""

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning("pyaudio not available. Wake word detection will be disabled.")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("numpy not available. Wake word detection will be disabled.")

try:
    from openwakeword.model import Model as OWWModel
    import openwakeword.utils as oww_utils
    OWW_AVAILABLE = True
except ImportError:
    OWW_AVAILABLE = False
    logger.warning(
        "openwakeword not available. Wake word detection will be disabled. "
        "Install with: pip install openwakeword"
    )


class WakeWordManager:
    """
    Continuous wake-word ("hotword") detector built on openWakeWord.
    """

    # openWakeWord expects 80ms frames of 16 kHz 16-bit mono audio.
    FRAME_SAMPLES = 1280
    SAMPLE_RATE = 16000

    def __init__(
        self,
        on_wake: Callable[[], None],
        model_name: str = "hey_jarvis",
        threshold: float = 0.5,
        device_index: Optional[int] = None,
        is_busy: Optional[Callable[[], bool]] = None,
        ack_player: Optional[Callable[[], None]] = None,
        cooldown_s: float = 2.0,
        max_busy_wait_s: float = 30.0,
    ):
        """
        Args:
            on_wake: Called (from the detector thread) right after the wake word
                is detected and the acknowledgment has played. Should kick off
                command capture.
            model_name: openWakeWord model to load (default "hey_jarvis").
            threshold: Detection score threshold in [0, 1].
            device_index: PyAudio input device index (None = system default).
            is_busy: Optional callable returning True while the host is still
                capturing/handling a command; scanning stays paused until False.
            ack_player: Optional callable that plays the acknowledgment sound.
                Called *before* on_wake. Should block until the sound finishes
                so it isn't picked up by the command microphone.
            cooldown_s: Minimum seconds between two detections.
            max_busy_wait_s: Safety cap on how long to wait for is_busy to clear.
        """
        self.on_wake = on_wake
        self.model_name = model_name
        self.threshold = threshold
        self.device_index = device_index
        self.is_busy = is_busy
        self.ack_player = ack_player
        self.cooldown_s = cooldown_s
        self.max_busy_wait_s = max_busy_wait_s

        self.available = OWW_AVAILABLE and PYAUDIO_AVAILABLE and NUMPY_AVAILABLE

        self._model = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._trigger_event = threading.Event()  # manual (test) trigger
        self._last_fire = 0.0

        # Diagnostics
        self.last_score = 0.0            # most recent prediction score
        self.last_detection_time = 0.0   # unix ts of last real detection
        self._peak_score = 0.0           # peak since last heartbeat
        self._last_heartbeat = 0.0

        if not self.available:
            missing = []
            if not OWW_AVAILABLE:
                missing.append("openwakeword")
            if not PYAUDIO_AVAILABLE:
                missing.append("pyaudio")
            if not NUMPY_AVAILABLE:
                missing.append("numpy")
            logger.warning(
                "WakeWordManager disabled - missing dependencies: %s",
                ", ".join(missing),
            )

    # ------------------------------------------------------------------ #
    # Model loading
    # ------------------------------------------------------------------ #
    def _ensure_model(self) -> bool:
        """Download (if needed) and load the wake word model."""
        if self._model is not None:
            return True
        try:
            # Idempotent - no-op once the model files are cached locally.
            try:
                oww_utils.download_models([self.model_name])
            except Exception as e:
                logger.warning("Could not verify wake word models (continuing): %s", e)

            self._model = OWWModel(
                wakeword_models=[self.model_name],
                inference_framework="onnx",
            )
            logger.info("Wake word model loaded: %s", list(self._model.models.keys()))
            return True
        except Exception as e:
            logger.error("Failed to load wake word model '%s': %s", self.model_name, e)
            self._model = None
            return False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        """Start continuous wake-word detection. Returns True on success."""
        if not self.available:
            logger.warning("Cannot start wake word - dependencies unavailable")
            return False
        if self._thread and self._thread.is_alive():
            logger.warning("Wake word detection already running")
            return False
        if not self._ensure_model():
            return False

        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Wake word detection started (model=%s, threshold=%.2f)",
                    self.model_name, self.threshold)
        return True

    def stop(self) -> bool:
        """Stop wake-word detection."""
        if not (self._thread and self._thread.is_alive()):
            return False
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        logger.info("Wake word detection stopped")
        return True

    def pause(self):
        """Temporarily pause scanning (mic is released while paused)."""
        self._pause_event.set()

    def resume(self):
        """Resume scanning after a pause."""
        self._pause_event.clear()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set())

    def trigger(self) -> bool:
        """Manually fire the wake flow (ack + command capture) for testing.

        Lets you verify the acknowledgment + listen + respond chain without
        relying on the detector actually hearing the wake word.
        """
        if not self.is_running():
            return False
        self._trigger_event.set()
        logger.info("Wake word manually triggered (test)")
        return True

    def set_device(self, device_index: Optional[int]):
        """Change the input device; restarts detection if currently running."""
        was_running = self.is_running()
        if was_running:
            self.stop()
        self.device_index = device_index
        logger.info("Wake word device set to: %s (None = system default)", device_index)
        if was_running:
            self.start()

    # ------------------------------------------------------------------ #
    # Detection loop
    # ------------------------------------------------------------------ #
    def _open_stream(self, pa):
        params = {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": self.SAMPLE_RATE,
            "input": True,
            "frames_per_buffer": self.FRAME_SAMPLES,
        }
        if self.device_index is not None:
            params["input_device_index"] = self.device_index
        return pa.open(**params)

    def _run(self):
        pa = pyaudio.PyAudio()
        stream = None

        def close_stream():
            nonlocal stream
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
                stream = None

        try:
            while not self._stop_event.is_set():
                # Paused: release the mic and idle.
                if self._pause_event.is_set():
                    close_stream()
                    time.sleep(0.1)
                    continue

                if stream is None:
                    try:
                        stream = self._open_stream(pa)
                    except Exception as e:
                        logger.error("Failed to open wake word audio stream: %s", e)
                        time.sleep(1.0)
                        continue

                try:
                    data = stream.read(self.FRAME_SAMPLES, exception_on_overflow=False)
                except Exception as e:
                    logger.warning("Wake word mic read error: %s", e)
                    close_stream()
                    time.sleep(0.2)
                    continue

                audio = np.frombuffer(data, dtype=np.int16)
                try:
                    scores = self._model.predict(audio)
                except Exception as e:
                    logger.warning("Wake word prediction error: %s", e)
                    continue

                score = scores.get(self.model_name)
                if score is None and scores:
                    score = max(scores.values())
                if score is None:
                    score = 0.0

                self.last_score = score
                self._peak_score = max(self._peak_score, score)

                now = time.time()

                # Near-miss logging: surfaces "I heard something close" so the
                # threshold / phrasing can be tuned from the console.
                if score >= 0.15 and score < self.threshold:
                    logger.info("Wake word near-miss: '%s' score=%.2f (threshold=%.2f) "
                                "- try saying it more clearly, or lower WAKE_WORD_THRESHOLD",
                                self.model_name, score, self.threshold)

                # Heartbeat every ~15s so you can confirm the detector is alive
                # and actually receiving audio (peak > 0 means the mic works).
                if now - self._last_heartbeat >= 15.0:
                    self._last_heartbeat = now
                    logger.debug("Wake word active (peak score last 15s=%.2f)", self._peak_score)
                    self._peak_score = 0.0

                manual = self._trigger_event.is_set()
                if manual or score >= self.threshold:
                    if not manual and (now - self._last_fire < self.cooldown_s):
                        continue
                    self._trigger_event.clear()
                    self._last_fire = now
                    self.last_detection_time = now
                    close_stream()  # free the mic for the ack + command capture
                    self._handle_detection(score if not manual else 1.0)

        finally:
            close_stream()
            try:
                pa.terminate()
            except Exception:
                pass
            try:
                if self._model is not None:
                    self._model.reset()
            except Exception:
                pass

    def _handle_detection(self, score: float):
        logger.info("Wake word detected: '%s' (score=%.2f)", self.model_name, score)

        # Reset the model's internal buffers so the tail of this utterance
        # doesn't immediately re-trigger on the next scan.
        try:
            self._model.reset()
        except Exception:
            pass

        # 1) Acknowledgment ("Yes?" / "Oui?"). Blocks until playback finishes.
        if self.ack_player is not None:
            try:
                self.ack_player()
            except Exception as e:
                logger.error("Wake acknowledgment failed: %s", e)

        # 2) Hand off to the host to capture the actual command.
        if self.on_wake is not None:
            try:
                self.on_wake()
            except Exception as e:
                logger.error("Wake on_wake handler failed: %s", e)

        # 3) Stay paused (mic released) while the host is busy handling the command.
        if self.is_busy is not None:
            start = time.time()
            time.sleep(0.2)  # give the host a moment to flip is_busy True
            while (
                self.is_busy()
                and not self._stop_event.is_set()
                and (time.time() - start) < self.max_busy_wait_s
            ):
                time.sleep(0.1)

        # 4) Short cooldown so we don't catch the tail of the response audio.
        time.sleep(self.cooldown_s)

    def get_status(self) -> dict:
        return {
            "available": self.available,
            "listening": self.is_running(),
            "paused": self._pause_event.is_set(),
            "model": self.model_name,
            "threshold": self.threshold,
            "last_score": round(self.last_score, 3),
            "last_detection_time": self.last_detection_time,
        }
