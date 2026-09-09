"""Text-to-speech via Kokoro (Apache 2.0). Not Jared Rhodenizer's — this file
only calls Kokoro's own public API, the same way any other project using
this library would.
"""

from __future__ import annotations

from typing import Iterator

import numpy as np

from .base import TTSEngine

KOKORO_SAMPLE_RATE = 24000  # Kokoro always generates at 24kHz.


class KokoroEngine(TTSEngine):
    """Wraps Kokoro's `KPipeline`.

    default_voice: any voice name Kokoro ships (its own convention: the
        first letter of the name picks the language — "b" for British
        English, "e" for Spanish, and so on).
    speed: passed straight through to Kokoro.

    Kokoro's pipeline is built once per language, not per voice, so this
    engine keeps one pipeline per language code and reuses it across calls
    instead of rebuilding on every utterance.
    """

    def __init__(self, default_voice: str = "bm_lewis", speed: float = 1.0) -> None:
        self._default_voice = default_voice
        self._speed = speed
        self._pipelines: dict[str, object] = {}

    def _pipeline_for(self, voice: str):
        lang_code = voice[0]
        if lang_code not in self._pipelines:
            from kokoro import KPipeline

            self._pipelines[lang_code] = KPipeline(lang_code=lang_code)
        return self._pipelines[lang_code]

    @property
    def sample_rate(self) -> int:
        return KOKORO_SAMPLE_RATE

    def synthesize(self, text: str, voice: str | None = None) -> Iterator[np.ndarray]:
        voice = voice or self._default_voice
        pipeline = self._pipeline_for(voice)
        for _, _, audio in pipeline(text, voice=voice, speed=self._speed):
            samples = np.asarray(audio, dtype=np.float32)
            if samples.size:
                yield (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)

    def unload(self) -> None:
        self._pipelines.clear()
