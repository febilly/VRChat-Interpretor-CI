from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RecognitionEvent:
    """Container for a single incremental recognition result."""

    text: str
    is_final: bool
    confidence: Optional[float] = None
    raw: Optional[Any] = None


class SpeechRecognitionCallback(ABC):
    """Callback interface for speech recognition events."""

    def on_session_started(self) -> None:  # pragma: no cover - optional hook
        """Called when the recognizer session starts."""
        pass

    def on_session_stopped(self) -> None:  # pragma: no cover - optional hook
        """Called when the recognizer session stops."""
        pass

    def on_error(self, error: Exception) -> None:  # pragma: no cover - optional hook
        """Called when an unrecoverable error occurs."""
        pass

    @abstractmethod
    def on_result(self, event: RecognitionEvent) -> None:
        """Called when new recognition text becomes available."""


class SpeechRecognizer(ABC):
    """Abstract base class for speech recognition backends."""

    @abstractmethod
    def set_callback(self, callback: SpeechRecognitionCallback) -> None:
        """Register the callback that will receive recognition events."""

    @abstractmethod
    def start(self) -> None:
        """Start the recognition session."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the recognition session."""

    @abstractmethod
    def send_audio_frame(self, data: bytes) -> None:
        """Send a chunk of audio data to the recognizer."""

    @abstractmethod
    def pause(self) -> None:
        """Temporarily pause recognition while keeping the session alive if possible."""

    @abstractmethod
    def resume(self) -> None:
        """Resume recognition after a previous pause."""

    @abstractmethod
    def get_last_request_id(self) -> Optional[str]:
        """Return the request identifier for the most recent session."""

    @abstractmethod
    def get_first_package_delay(self) -> Optional[int]:
        """Latency in milliseconds for the first package, if available."""

    @abstractmethod
    def get_last_package_delay(self) -> Optional[int]:
        """Latency in milliseconds for the last package, if available."""
