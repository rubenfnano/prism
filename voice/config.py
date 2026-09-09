"""The voice piece's own config file (voice.json).

Deliberately separate from anything about push-to-talk keys, permissions, or
Claude Code — this module knows only about which engines are chosen and
their own settings. Wiring lives elsewhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_STT_OPTIONS = {"model_size": "small"}
DEFAULT_TTS_OPTIONS = {"default_voice": "bm_lewis"}


@dataclass
class VoiceConfig:
    stt_engine: str = "whisper"
    stt_options: dict = field(default_factory=lambda: dict(DEFAULT_STT_OPTIONS))
    tts_engine: str = "kokoro"
    tts_options: dict = field(default_factory=lambda: dict(DEFAULT_TTS_OPTIONS))

    @classmethod
    def load(cls, path: Path) -> "VoiceConfig":
        """Read voice.json if it exists; fall back to the defaults above
        (Whisper + Kokoro) for anything missing, so a partial or absent
        config file never crashes the voice piece.
        """
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            stt_engine=data.get("stt_engine", cls.stt_engine),
            stt_options=data.get("stt_options") or dict(DEFAULT_STT_OPTIONS),
            tts_engine=data.get("tts_engine", cls.tts_engine),
            tts_options=data.get("tts_options") or dict(DEFAULT_TTS_OPTIONS),
        )

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "stt_engine": self.stt_engine,
                    "stt_options": self.stt_options,
                    "tts_engine": self.tts_engine,
                    "tts_options": self.tts_options,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
