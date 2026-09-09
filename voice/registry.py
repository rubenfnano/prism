"""The one place that knows which engine names exist.

This is the whole point of the interface: adding an engine means adding one
entry here and one new file under engines/stt/ or engines/tts/ — never
touching an engine that already works, and never hardcoding a choice
anywhere else in the voice piece (the mistake this design deliberately
avoids).
"""

from __future__ import annotations

from typing import Callable

from .engines.stt.base import STTEngine
from .engines.stt.whisper_engine import WhisperEngine
from .engines.tts.base import TTSEngine
from .engines.tts.kokoro_engine import KokoroEngine

_STT_ENGINES: dict[str, Callable[..., STTEngine]] = {
    "whisper": WhisperEngine,
    # "parakeet": ...   # candidato evaluado, sin implementar todavía
}

_TTS_ENGINES: dict[str, Callable[..., TTSEngine]] = {
    "kokoro": KokoroEngine,
    # "chatterbox": ... # candidato evaluado, sin implementar todavía
    # "elevenlabs": ...  # cuenta propia del usuario, sin implementar todavía
}


def stt_engine(name: str, **kwargs) -> STTEngine:
    try:
        factory = _STT_ENGINES[name]
    except KeyError:
        raise ValueError(
            f"Motor de voz-a-texto desconocido: '{name}'. "
            f"Disponibles: {', '.join(sorted(_STT_ENGINES))}"
        ) from None
    return factory(**kwargs)


def tts_engine(name: str, **kwargs) -> TTSEngine:
    try:
        factory = _TTS_ENGINES[name]
    except KeyError:
        raise ValueError(
            f"Motor de texto-a-voz desconocido: '{name}'. "
            f"Disponibles: {', '.join(sorted(_TTS_ENGINES))}"
        ) from None
    return factory(**kwargs)


def available_stt_engines() -> list[str]:
    return sorted(_STT_ENGINES)


def available_tts_engines() -> list[str]:
    return sorted(_TTS_ENGINES)
