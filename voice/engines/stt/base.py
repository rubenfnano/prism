"""Base interface every speech-to-text engine must implement.

Adding a new STT engine means writing one new file in this folder that
implements this class — never editing an existing engine, and never adding
a special case anywhere else in the voice piece.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class STTEngine(ABC):
    """Turns one recorded utterance into text.

    Implementations load their model lazily, on first call to `transcribe`,
    not at construction time — picking an engine in config should cost
    nothing until it's actually used.
    """

    @abstractmethod
    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None = None,
    ) -> str:
        """Transcribe one utterance already captured in memory.

        audio: mono float32 samples in [-1.0, 1.0].
        sample_rate: the rate `audio` was recorded at, in Hz. An engine that
            needs a specific rate resamples internally; callers never have
            to know which rate any given engine wants.
        language: an ISO 639-1 code (e.g. "es"), or None to let the engine
            detect the spoken language itself.
        """
        raise NotImplementedError

    def unload(self) -> None:
        """Release any loaded model and free its memory.

        Optional to override — the default does nothing, which is correct
        for an engine that has nothing to release.
        """
        return None
