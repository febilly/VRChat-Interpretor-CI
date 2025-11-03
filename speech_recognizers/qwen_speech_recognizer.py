from __future__ import annotations

import base64
from contextlib import suppress
import threading
from typing import Any, Dict, Optional

from dashscope.audio.qwen_omni import (
    MultiModality,
    OmniRealtimeCallback,
    OmniRealtimeConversation,
)

try:
    from dashscope.audio.qwen_omni.omni_realtime import TranscriptionParams
except ImportError:  # pragma: no cover
    class TranscriptionParams:  # type: ignore[override]
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

from .base_speech_recognizer import (
    RecognitionEvent,
    SpeechRecognitionCallback,
    SpeechRecognizer,
)

__all__ = ["QwenSpeechRecognizer"]


class _QwenOmniCallbackAdapter(OmniRealtimeCallback):
    """Bridge Qwen realtime callbacks to the generic recognizer callback."""

    def __init__(
        self,
        recognizer: "QwenSpeechRecognizer",
        user_callback: SpeechRecognitionCallback,
    ) -> None:
        self._recognizer = recognizer
        self._user_callback = user_callback
        self._conversation: Optional[OmniRealtimeConversation] = None
        self._items: Dict[str, Dict[str, str]] = {}

    def attach_conversation(self, conversation: OmniRealtimeConversation) -> None:
        self._conversation = conversation

    def detach(self) -> None:
        self._conversation = None

    # ------------------------------------------------------------------
    # OmniRealtimeCallback interface
    # ------------------------------------------------------------------
    def on_open(self) -> None:  # type: ignore[override]
        self._user_callback.on_session_started()

    def on_close(self, code, msg) -> None:  # type: ignore[override]
        _ = (code, msg)  # unused metadata
        self._user_callback.on_session_stopped()
        self._recognizer._notify_closed()

    def on_event(self, message: Dict[str, Any]) -> None:  # type: ignore[override]
        if not isinstance(message, dict):
            return
        event_type = message.get("type")
        if event_type == "session.created":
            self._handle_session_created(message)
        elif event_type == "session.updated":
            self._handle_session_updated(message)
        elif event_type == "conversation.item.input_audio_transcription.text":
            self._handle_transcription_text(message)
        elif event_type == "conversation.item.input_audio_transcription.completed":
            self._handle_transcription_completed(message)
        elif event_type == "conversation.item.input_audio_transcription.failed":
            self._handle_transcription_failed(message)
        elif event_type == "response.done":
            self._recognizer._update_metrics(self._conversation)
        elif event_type == "error":
            self._handle_error(message)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _handle_session_created(self, message: Dict[str, Any]) -> None:
        session = message.get("session") or {}
        session_id = session.get("id")
        if session_id:
            self._recognizer._update_session_id(str(session_id))

    def _handle_session_updated(self, message: Dict[str, Any]) -> None:
        session = message.get("session") or {}
        session_id = session.get("id")
        if session_id:
            self._recognizer._update_session_id(str(session_id))

    def _handle_transcription_text(self, message: Dict[str, Any]) -> None:
        item_id = message.get("item_id")
        if not item_id:
            return
        fixed = message.get("text") or ""
        stash = message.get("stash") or ""
        combined = f"{fixed}{stash}"
        print(f"Intermediate recognized text: {combined}")
        self._items[item_id] = {"fixed": fixed, "stash": stash}
        if not combined:
            return
        event = RecognitionEvent(text=combined, is_final=False, raw=message)
        self._user_callback.on_result(event)

    def _handle_transcription_completed(self, message: Dict[str, Any]) -> None:
        item_id = message.get("item_id")
        transcript = message.get("transcript") or ""
        if not transcript and item_id and item_id in self._items:
            cache = self._items[item_id]
            transcript = f"{cache.get('fixed', '')}{cache.get('stash', '')}"
        if transcript:
            event = RecognitionEvent(text=transcript, is_final=True, raw=message)
            self._user_callback.on_result(event)
        if item_id:
            self._items.pop(item_id, None)

    def _handle_transcription_failed(self, message: Dict[str, Any]) -> None:
        error = message.get("error") or {}
        detail = error.get("message") or "Recognition failed"
        code = error.get("code")
        if code:
            detail = f"{detail} (code={code})"
        self._user_callback.on_error(RuntimeError(detail))

    def _handle_error(self, message: Dict[str, Any]) -> None:
        error = message.get("error") or {}
        detail = error.get("message") or "Unknown error"
        code = error.get("code")
        if code:
            detail = f"{detail} (code={code})"
        event_id = error.get("event_id")
        if event_id:
            detail = f"{detail} [event_id={event_id}]"
        self._user_callback.on_error(RuntimeError(detail))


class QwenSpeechRecognizer(SpeechRecognizer):
    """Speech recognizer backed by the Qwen realtime ASR API."""

    def __init__(self, callback: SpeechRecognitionCallback, **recognition_kwargs: Any) -> None:
        self._lock = threading.Lock()
        self._conversation: Optional[OmniRealtimeConversation] = None
        self._adapter: Optional[_QwenOmniCallbackAdapter] = None
        self._callback: Optional[SpeechRecognitionCallback] = None
        self._session_id: Optional[str] = None
        self._last_response_id: Optional[str] = None
        self._last_first_text_delay: Optional[int] = None
        self._last_first_audio_delay: Optional[int] = None
        self._paused: bool = False

        options = dict(recognition_kwargs)
        self._model = options.pop("model", "qwen3-asr-flash-realtime")
        self._url = options.pop("url", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime")
        self._enable_turn_detection: Optional[bool] = options.pop("enable_turn_detection", True)
        self._turn_detection_threshold: Optional[float] = options.pop("turn_detection_threshold", 0.2)
        self._turn_detection_silence_duration_ms: Optional[int] = options.pop(
            "turn_detection_silence_duration_ms",
            800,
        )
        self._input_audio_format = options.pop("input_audio_format", "pcm")
        self._sample_rate = options.pop("sample_rate", 16000)
        self._language = options.pop("language", None)
        self._corpus_text = options.pop("corpus_text", None)
        self._enable_input_audio_transcription = options.pop("enable_input_audio_transcription", True)
        self._transcription_params: Optional[TranscriptionParams] = options.pop("transcription_params", None)
        self._conversation_kwargs = dict(options.pop("conversation_kwargs", {}))
        self._update_session_overrides = dict(options.pop("update_session_kwargs", {}))
        if options:
            self._update_session_overrides.update(options)
        if "model" not in self._conversation_kwargs:
            self._conversation_kwargs["model"] = self._model
        if "url" not in self._conversation_kwargs:
            self._conversation_kwargs["url"] = self._url

        self.set_callback(callback)

    # ------------------------------------------------------------------
    # SpeechRecognizer interface
    # ------------------------------------------------------------------
    def set_callback(self, callback: SpeechRecognitionCallback) -> None:
        if callback is None:
            raise ValueError("callback must not be None")
        with self._lock:
            if self._conversation is not None:
                raise RuntimeError("Callback already configured; create a new recognizer instance instead.")
            self._callback = callback

    def start(self) -> None:
        with self._lock:
            if self._conversation is not None:
                return
            adapter = self._create_adapter()
            conversation = OmniRealtimeConversation(callback=adapter, **self._conversation_kwargs)
            adapter.attach_conversation(conversation)
            self._conversation = conversation
            self._adapter = adapter
            self._session_id = None
            self._last_response_id = None
            self._last_first_text_delay = None
            self._last_first_audio_delay = None
            self._paused = False

        conversation = self._conversation
        assert conversation is not None  # for type checkers
        try:
            conversation.connect()
            transcription_params = self._resolve_transcription_params()
            update_kwargs: Dict[str, Any] = {
                "output_modalities": [MultiModality.TEXT],
                "enable_input_audio_transcription": self._enable_input_audio_transcription,
                "transcription_params": transcription_params,
            }
            if self._enable_turn_detection is not None:
                update_kwargs["enable_turn_detection"] = self._enable_turn_detection
            if self._enable_turn_detection:
                update_kwargs.setdefault("turn_detection_type", "server_vad")
                if self._turn_detection_threshold is not None:
                    update_kwargs.setdefault("turn_detection_threshold", self._turn_detection_threshold)
                if self._turn_detection_silence_duration_ms is not None:
                    update_kwargs.setdefault(
                        "turn_detection_silence_duration_ms",
                        self._turn_detection_silence_duration_ms,
                    )
            else:
                update_kwargs.setdefault("turn_detection_type", None)
            update_kwargs.update(self._update_session_overrides)
            conversation.update_session(**update_kwargs)
        except Exception:
            self._teardown_conversation(close=True)
            raise

    def stop(self) -> None:
        conversation = self._teardown_conversation(close=False)
        if conversation is None:
            return
        if not self._enable_turn_detection:
            with suppress(Exception):
                conversation.commit()
        with suppress(Exception):
            conversation.close()
        with self._lock:
            self._paused = False

    def send_audio_frame(self, data: bytes) -> None:
        if not data:
            return
        with self._lock:
            if self._paused:
                return
        conversation = self._require_conversation()
        audio_b64 = base64.b64encode(data).decode("ascii")
        conversation.append_audio(audio_b64)

    def pause(self) -> None:
        conversation: Optional[OmniRealtimeConversation] = None
        with self._lock:
            if self._paused:
                return
            self._paused = True
            conversation = self._conversation
        if conversation is not None:
            # VAD和手动commit不能同时使用
            if self._enable_turn_detection:
                # 启用VAD时，发送静音音频触发断句
                # 静音时长应比VAD的静音检测时长稍长，确保触发断句
                with suppress(Exception):
                    silence_duration_ms = self._turn_detection_silence_duration_ms or 800
                    # 多加200ms确保触发
                    silence_duration_ms += 200
                    sample_rate = self._sample_rate or 16000
                    # 计算需要的静音帧数
                    silence_frames = int(sample_rate * silence_duration_ms / 1000)
                    # 生成静音数据（16位PCM，单声道）
                    silence_data = b'\x00' * (silence_frames * 2)
                    audio_b64 = base64.b64encode(silence_data).decode("ascii")
                    conversation.append_audio(audio_b64)
            else:
                # 禁用VAD时，手动调用commit触发断句
                with suppress(Exception):
                    conversation.commit()

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def get_last_request_id(self) -> Optional[str]:
        with self._lock:
            return self._last_response_id or self._session_id

    def get_first_package_delay(self) -> Optional[int]:
        with self._lock:
            return self._last_first_text_delay

    def get_last_package_delay(self) -> Optional[int]:
        with self._lock:
            return self._last_first_audio_delay

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _create_adapter(self) -> _QwenOmniCallbackAdapter:
        if self._callback is None:
            raise RuntimeError("Callback not configured; call set_callback first.")
        return _QwenOmniCallbackAdapter(self, self._callback)

    def _require_conversation(self) -> OmniRealtimeConversation:
        with self._lock:
            conversation = self._conversation
        if conversation is None:
            raise RuntimeError("Speech recognizer not started; call start() first.")
        return conversation

    def _resolve_transcription_params(self) -> TranscriptionParams:
        if self._transcription_params is not None:
            return self._transcription_params
        params: Dict[str, Any] = {
            "sample_rate": self._sample_rate,
            "input_audio_format": self._input_audio_format,
        }
        if self._language:
            params["language"] = self._language
        if self._corpus_text:
            params["corpus_text"] = self._corpus_text
        return TranscriptionParams(**params)

    def _teardown_conversation(self, *, close: bool) -> Optional[OmniRealtimeConversation]:
        with self._lock:
            conversation = self._conversation
            if conversation is None:
                return None
            adapter = self._adapter
            if adapter is not None:
                adapter.detach()
            self._conversation = None
            self._adapter = None
            self._paused = False
        if close:
            with suppress(Exception):
                conversation.close()
            return None
        return conversation

    def _update_metrics(self, conversation: Optional[OmniRealtimeConversation]) -> None:
        conv = conversation or self._conversation
        if conv is None:
            return
        response_id: Optional[str] = None
        first_text_delay: Optional[int] = None
        first_audio_delay: Optional[int] = None
        with suppress(Exception):
            response_id = conv.get_last_response_id()
        with suppress(Exception):
            first_text_delay = conv.get_last_first_text_delay()
        with suppress(Exception):
            first_audio_delay = conv.get_last_first_audio_delay()
        with self._lock:
            if response_id is not None:
                self._last_response_id = response_id
            if first_text_delay is not None:
                self._last_first_text_delay = first_text_delay
            if first_audio_delay is not None:
                self._last_first_audio_delay = first_audio_delay

    def _update_session_id(self, session_id: str) -> None:
        with self._lock:
            self._session_id = session_id

    def _notify_closed(self) -> None:
        with self._lock:
            self._conversation = None
            self._adapter = None
            self._paused = False
