"""Base interface every text-to-speech engine must implement.

Adding a new TTS engine means writing one new file in this folder that
implements this class — never editing an existing engine, and never adding
a special case anywhere else in the voice piece.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

import numpy as np


class TTSEngine(ABC):
    """Turns text into streamed audio.

    Implementations yield audio as it's generated, so playback can start
    before the whole utterance has finished synthesizing.
    """

    @abstractmethod
    def synthesize(self, text: str, voice: str | None = None) -> Iterator[np.ndarray]:
        """Synthesize one utterance, yielding int16 PCM chunks as they're ready.

        voice: an engine-specific voice identifier, or None for the engine's
            own configured default.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """The sample rate, in Hz, of every PCM chunk this engine yields."""
        raise NotImplementedError

    def unload(self) -> None:
        """Release any loaded model and free its memory.

        Optional to override — the default does nothing, which is correct
        for an engine that has nothing to release.
        """
        return None
