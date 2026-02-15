"""
Mistral Voxtral Speech-to-Text Manager

Handles real-time speech-to-text transcription using Mistral's Voxtral API.
Captures microphone audio via PyAudio and streams it to the Mistral API for
real-time transcription.
"""

import asyncio
import threading
import logging
from queue import Queue
from typing import AsyncIterator, Optional, Callable
import os
import struct
import math
import time

try:
    from mistralai import Mistral
    from mistralai.extra.realtime import UnknownRealtimeEvent
    from mistralai.models import (
        AudioFormat,
        RealtimeTranscriptionError,
        RealtimeTranscriptionSessionCreated,
        TranscriptionStreamDone,
        TranscriptionStreamTextDelta
    )
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False
    logging.warning("mistralai package not available. STT features will be disabled.")

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("pyaudio package not available. STT features will be disabled.")


logger = logging.getLogger(__name__)


class MistralSTTManager:
    """
    Manages speech-to-text transcription using Mistral Voxtral.
    """

    def __init__(self, api_key: str, sample_rate: int = 16000, chunk_duration_ms: int = 480):
        """
        Initialize the STT manager.

        Args:
            api_key: Mistral API key
            sample_rate: Audio sample rate in Hz (default: 16000)
            chunk_duration_ms: Audio chunk duration in milliseconds (default: 480)
        """
        if not MISTRAL_AVAILABLE:
            raise ImportError("mistralai package is required for STT. Install with: pip install 'mistralai[realtime]'")

        if not PYAUDIO_AVAILABLE:
            raise ImportError("pyaudio package is required for STT. Install with: pip install pyaudio")

        self.api_key = api_key
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.model = "voxtral-mini-transcribe-realtime-2602"

        # Initialize Mistral client
        self.client = Mistral(api_key=self.api_key)

        # Audio format (PCM 16-bit mono)
        self.audio_format = AudioFormat(
            encoding="pcm_s16le",
            sample_rate=self.sample_rate
        )

        # State management
        self.is_listening = False
        self.is_paused = False
        self.selected_device_index = None  # None = system default
        self._listen_thread = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

        # Event queues for broadcasting transcription events
        self.event_queues = []

        # Callback for transcription events
        self.on_transcription_partial: Optional[Callable[[str], None]] = None
        self.on_transcription_complete: Optional[Callable[[str], None]] = None
        self.on_transcription_error: Optional[Callable[[str], None]] = None

        # Transcript buffer (for accumulating partial transcriptions)
        self._current_transcript = ""

        logger.info(f"MistralSTTManager initialized with model: {self.model}")

    @staticmethod
    def list_audio_devices():
        """
        List all available audio input devices.

        Returns:
            list: List of device info dicts with index, name, channels, sample_rate
        """
        if not PYAUDIO_AVAILABLE:
            return []

        p = pyaudio.PyAudio()
        devices = []

        try:
            for i in range(p.get_device_count()):
                try:
                    info = p.get_device_info_by_index(i)
                    # Only include input devices
                    if info['maxInputChannels'] > 0:
                        devices.append({
                            'index': i,
                            'name': info['name'],
                            'channels': info['maxInputChannels'],
                            'sample_rate': int(info['defaultSampleRate'])
                        })
                except Exception as e:
                    logger.warning(f"Failed to get info for device {i}: {e}")
        finally:
            p.terminate()

        return devices

    def calculate_rms(self, audio_data: bytes) -> int:
        """
        Calculate RMS (Root Mean Square) amplitude for volume level.

        Args:
            audio_data: PCM 16-bit audio data

        Returns:
            int: Volume level 0-100
        """
        try:
            # Convert bytes to 16-bit integers
            count = len(audio_data) // 2
            if count == 0:
                return 0

            format_str = f"{count}h"
            shorts = struct.unpack(format_str, audio_data)

            # Calculate RMS
            sum_squares = sum(s ** 2 for s in shorts)
            rms = math.sqrt(sum_squares / count)

            # Normalize to 0-100 (assuming max amplitude is 32767 for 16-bit)
            # Use 300x multiplier for better sensitivity to normal speech
            volume_percent = min(100, int((rms / 32767.0) * 300))
            return volume_percent
        except Exception as e:
            logger.error(f"RMS calculation error: {e}")
            return 0

    async def _iter_microphone(self, device_index=None) -> AsyncIterator[bytes]:
        """
        Yield microphone PCM chunks using PyAudio (16-bit mono).
        Encoding is always pcm_s16le.

        Args:
            device_index: PyAudio device index (None = system default)
        """
        p = pyaudio.PyAudio()
        chunk_samples = int(self.sample_rate * self.chunk_duration_ms / 1000)

        try:
            # Open stream with specified device
            stream_params = {
                'format': pyaudio.paInt16,
                'channels': 1,
                'rate': self.sample_rate,
                'input': True,
                'frames_per_buffer': chunk_samples,
            }

            # Add device index if specified
            if device_index is not None:
                stream_params['input_device_index'] = device_index
                logger.info(f"Opening audio stream with device index: {device_index}")

            stream = p.open(**stream_params)

            loop = asyncio.get_running_loop()
            last_volume_broadcast = time.time()

            while not self._stop_event.is_set():
                # Check if paused
                while self.is_paused and not self._stop_event.is_set():
                    await asyncio.sleep(0.1)

                if self._stop_event.is_set():
                    break

                try:
                    # stream.read is blocking; run it off-thread
                    data = await loop.run_in_executor(None, stream.read, chunk_samples, False)

                    # Calculate and broadcast volume level at 10Hz
                    current_time = time.time()
                    if current_time - last_volume_broadcast > 0.1:  # 100ms = 10Hz
                        volume = self.calculate_rms(data)
                        self._broadcast_event({
                            "type": "audio_level",
                            "level": volume
                        })
                        last_volume_broadcast = current_time

                    yield data
                except Exception as e:
                    logger.error(f"Error reading from microphone: {e}")
                    break

        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            logger.info("Microphone stream closed")

    async def _transcribe_stream(self):
        """
        Main transcription loop. Captures audio and streams to Mistral API.
        """
        try:
            audio_stream = self._iter_microphone(device_index=self.selected_device_index)
            self._current_transcript = ""  # Use instance variable for tracking

            logger.info("Starting transcription stream...")
            self._broadcast_event({"type": "transcription_started"})

            async for event in self.client.audio.realtime.transcribe_stream(
                audio_stream=audio_stream,
                model=self.model,
                audio_format=self.audio_format,
            ):
                if isinstance(event, RealtimeTranscriptionSessionCreated):
                    logger.info("Transcription session created")
                    self._broadcast_event({"type": "session_created"})

                elif isinstance(event, TranscriptionStreamTextDelta):
                    # Partial transcription (real-time delta)
                    self._current_transcript += event.text
                    logger.debug(f"Transcription delta: {event.text}")

                    # Broadcast partial transcription
                    self._broadcast_event({
                        "type": "transcription_partial",
                        "text": event.text,
                        "full_text": self._current_transcript
                    })

                    if self.on_transcription_partial:
                        self.on_transcription_partial(event.text)

                elif isinstance(event, TranscriptionStreamDone):
                    # Transcription complete
                    logger.info(f"Transcription complete: {self._current_transcript}")

                    # Broadcast complete transcription
                    self._broadcast_event({
                        "type": "transcription_complete",
                        "text": self._current_transcript
                    })

                    if self.on_transcription_complete:
                        self.on_transcription_complete(self._current_transcript)

                    # Reset for next phrase
                    self._current_transcript = ""

                elif isinstance(event, RealtimeTranscriptionError):
                    error_msg = str(event)
                    logger.error(f"Transcription error: {error_msg}")

                    self._broadcast_event({
                        "type": "transcription_error",
                        "error": error_msg
                    })

                    if self.on_transcription_error:
                        self.on_transcription_error(error_msg)

                elif isinstance(event, UnknownRealtimeEvent):
                    logger.warning(f"Unknown event: {event}")
                    continue

        except Exception as e:
            logger.error(f"Transcription stream error: {e}")
            self._broadcast_event({
                "type": "transcription_error",
                "error": str(e)
            })
        finally:
            self.is_listening = False
            logger.info("Transcription stream ended")

    def _transcribe_thread_target(self):
        """
        Thread target for running the async transcription loop.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._transcribe_stream())
        except Exception as e:
            logger.error(f"Transcription thread error: {e}")
        finally:
            loop.close()

    def start_listening(self) -> bool:
        """
        Start capturing microphone audio and transcribing.

        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.is_listening:
            logger.warning("Already listening")
            return False

        try:
            self.is_listening = True
            self.is_paused = False
            self._stop_event.clear()
            self._pause_event.clear()

            # Start transcription thread
            self._listen_thread = threading.Thread(
                target=self._transcribe_thread_target,
                daemon=True
            )
            self._listen_thread.start()

            logger.info("Started listening")
            return True

        except Exception as e:
            logger.error(f"Failed to start listening: {e}")
            self.is_listening = False
            return False

    def stop_listening(self) -> bool:
        """
        Stop capturing microphone audio.

        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.is_listening:
            logger.warning("Not currently listening")
            return False

        try:
            self._stop_event.set()
            self.is_listening = False
            self.is_paused = False

            # Wait for thread to finish (with timeout)
            if self._listen_thread and self._listen_thread.is_alive():
                self._listen_thread.join(timeout=2.0)

            logger.info("Stopped listening")
            self._broadcast_event({"type": "transcription_stopped"})
            return True

        except Exception as e:
            logger.error(f"Failed to stop listening: {e}")
            return False

    def pause_listening(self) -> bool:
        """
        Temporarily pause transcription (e.g., while AI is speaking).

        Returns:
            bool: True if paused successfully, False otherwise
        """
        if not self.is_listening:
            logger.warning("Not currently listening, cannot pause")
            return False

        if self.is_paused:
            logger.warning("Already paused")
            return False

        self.is_paused = True
        logger.info("Paused listening")
        self._broadcast_event({"type": "transcription_paused"})
        return True

    def resume_listening(self) -> bool:
        """
        Resume transcription after pause.

        Returns:
            bool: True if resumed successfully, False otherwise
        """
        if not self.is_listening:
            logger.warning("Not currently listening, cannot resume")
            return False

        if not self.is_paused:
            logger.warning("Not currently paused")
            return False

        self.is_paused = False
        logger.info("Resumed listening")
        self._broadcast_event({"type": "transcription_resumed"})
        return True

    def get_status(self) -> dict:
        """
        Get current STT status.

        Returns:
            dict: Status information
        """
        return {
            "is_listening": self.is_listening,
            "is_paused": self.is_paused,
            "model": self.model,
            "sample_rate": self.sample_rate
        }

    def clear_transcript_buffer(self):
        """
        Manually clear the transcript buffer.
        Useful when switching modes or starting fresh.
        """
        self._current_transcript = ""
        logger.info("Transcript buffer cleared")
        self._broadcast_event({"type": "transcript_cleared"})

    def _broadcast_event(self, event: dict):
        """
        Broadcast an event to all connected clients via SSE queues.

        Args:
            event: Event data to broadcast
        """
        dead_queues = []
        for queue in self.event_queues:
            try:
                queue.put_nowait(event)
            except Exception as e:
                logger.warning(f"Failed to broadcast to queue: {e}")
                dead_queues.append(queue)

        # Clean up dead queues
        for dead_queue in dead_queues:
            try:
                self.event_queues.remove(dead_queue)
            except ValueError:
                pass

    def add_event_queue(self, queue: Queue):
        """
        Add a queue for broadcasting transcription events.

        Args:
            queue: Queue to add
        """
        self.event_queues.append(queue)

    def remove_event_queue(self, queue: Queue):
        """
        Remove a queue from broadcasting.

        Args:
            queue: Queue to remove
        """
        try:
            self.event_queues.remove(queue)
        except ValueError:
            pass

    def set_device(self, device_index: Optional[int]) -> bool:
        """
        Set the microphone device to use.

        Args:
            device_index: PyAudio device index (None = system default)

        Returns:
            bool: True if device set successfully
        """
        was_listening = self.is_listening

        # Stop listening if currently active
        if was_listening:
            self.stop_listening()

        # Update device
        self.selected_device_index = device_index
        logger.info(f"STT device set to: {device_index} (None = system default)")

        # Restart listening if it was active
        if was_listening:
            return self.start_listening()

        return True

    def get_current_device(self) -> Optional[dict]:
        """
        Get info about the currently selected device.

        Returns:
            dict: Device info or None if using system default
        """
        if self.selected_device_index is None:
            return None

        devices = self.list_audio_devices()
        for device in devices:
            if device['index'] == self.selected_device_index:
                return device

        return None

    def shutdown(self):
        """
        Shutdown the STT manager gracefully.
        """
        logger.info("Shutting down STT manager")
        if self.is_listening:
            self.stop_listening()
        self.event_queues.clear()
