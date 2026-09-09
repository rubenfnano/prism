"""PRISM voice: speech-to-text and text-to-speech behind one swappable interface.

Public API:
    from voice import VoiceConfig, stt_engine, tts_engine

Example:
    cfg = VoiceConfig.load(Path("voice.json"))
    stt = stt_engine(cfg.stt_engine, **cfg.stt_options)
    tts = tts_engine(cfg.tts_engine, **cfg.tts_options)
"""

from .config import VoiceConfig
from .registry import (
    available_stt_engines,
    available_tts_engines,
    stt_engine,
    tts_engine,
)

__all__ = [
    "VoiceConfig",
    "stt_engine",
    "tts_engine",
    "available_stt_engines",
    "available_tts_engines",
]
