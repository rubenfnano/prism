"""Speech-to-text via faster-whisper (MIT), running OpenAI's Whisper models
(MIT). Neither library is Jared Rhodenizer's — this file only calls their
public API, the same way any other project using these libraries would.
"""

from __future__ import annotations

import numpy as np

from .base import STTEngine

WHISPER_SAMPLE_RATE = 16000  # Whisper models are trained on 16kHz audio.


class WhisperEngine(STTEngine):
    """Wraps faster-whisper's `WhisperModel`.

    model_size: any size faster-whisper accepts ("tiny", "base", "small",
        "medium", "large-v3", ...) — "small" is a reasonable default: fast
        enough on CPU, accurate enough for a conversation.
    device / compute_type: passed straight through to faster-whisper. If the
        requested combination isn't available (no GPU, or a compute type the
        installed CTranslate2 build doesn't support), this engine retries
        once on CPU with int8 instead of failing outright.
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "default",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        try:
            self._model = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type
            )
        except Exception:
            self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None = None,
    ) -> str:
        self._load()
        if sample_rate != WHISPER_SAMPLE_RATE:
            audio = _resample(audio, sample_rate, WHISPER_SAMPLE_RATE)
        segments, _ = self._model.transcribe(audio, language=language, vad_filter=True)
        return "".join(segment.text for segment in segments).strip()

    def unload(self) -> None:
        self._model = None


def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Linear resampling — good enough for speech, no extra dependency
    beyond numpy. Swapped for something better later if quality demands it.
    """
    if from_rate == to_rate:
        return audio
    duration = audio.shape[0] / from_rate
    target_len = int(round(duration * to_rate))
    original_x = np.linspace(0, duration, num=audio.shape[0], endpoint=False)
    target_x = np.linspace(0, duration, num=target_len, endpoint=False)
    return np.interp(target_x, original_x, audio).astype(np.float32)
