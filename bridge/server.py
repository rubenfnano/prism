"""PRISM: the bridge (Fase 4) — HTTP polling, no WebSocket.

Rewritten 2026-09-10 after a WebSocket-based version kept breaking in
ways that trace back to one root cause: a persistent connection means
the server has to track WHICH tab to answer, and that breaks the moment
there's more than one (two of Rubén's own browser tabs, or — the actual
bug that triggered this rewrite — a developer's automated test running
against the same live server a person is also using for real, with
their two sessions' replies literally crossing).

The fix is to have no connection to mis-attach in the first place, the
same way ai-visualizer avoids it: state lives on the SERVER, exposed
over plain HTTP, and every client (however many tabs, however many
callers) polls it independently. Nothing to attach, nothing to
mis-route — inspired by that pattern, not its code: this file shares
no lines with ai-visualizer/server.py, and the actual work here (voice
decode, the SDK session, the permission gate) has no equivalent there
at all.

Runs INSIDE the voice piece's own venv (see voice/pyproject.toml) —
avoids installing torch/whisper in two separate environments.

Endpoints:
  GET  /events?since=<id>   new events since <id>, plus current state.
                             Polled continuously by the face (~3-4x/sec).
  POST /voice/start         opens the mic (sounddevice, native OS
                             capture — NOT the browser's MediaRecorder,
                             switched 2026-09-10: a webm blob from the
                             browser had no silence trimmed out of it,
                             and that was hurting transcription badly)
                             and starts buffering.
  POST /voice/stop          closes the mic, trims silence with
                             webrtcvad, and processes the turn in the
                             background — the result shows up via
                             /events, same as everything else.
  POST /chat    ({"text": "..."} or {"type": "greet"})
                             a typed turn, same background-then-poll
                             shape as voice. Text never speaks.
  GET  /audio_stream        raw int16 PCM for the CURRENT voice turn,
                             streamed live as Kokoro generates it — the
                             face opens this the instant it submits a
                             voice turn, doesn't wait for a poll to
                             find out there's something to hear.
  GET  /                    the face, served as static files.

Permission handling mirrors backtalk's spoken gate (brain.py /
make_permission_gate in main.py) in SPIRIT — the model pauses on a tool
call until a person answers — but the question is just another /events
entry, and the answer is just another /chat or /voice turn (checked
against whatever confirmation is currently pending), not anything
socket-specific.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import re
import sys
import uuid
from pathlib import Path

import numpy as np
import sounddevice as sd
import webrtcvad
from aiohttp import web
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
)

HOME_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent

# voice/ has its own __init__.py (a real package, for its relative
# imports like `from .engines.stt.base import ...` to work) — so the
# home dir goes on the path, and it's imported AS a package, never
# voice's internals imported standalone.
sys.path.insert(0, str(HOME_DIR))
from voice import VoiceConfig, stt_engine, tts_engine  # noqa: E402

FACE_DIR = HOME_DIR / "cara"
VOICE_CONFIG_PATH = HOME_DIR / "voice" / "voice.json"
PERMISSIONS_PATH = HOME_DIR / "permissions.json"
LANGUAGE_PATH = HOME_DIR / "language.json"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8793

GREETING_PROMPT = (
    "Preséntate con tu saludo inicial de sesión, tal como manda tu propio "
    "CLAUDE.md (breve, distinto cada vez, con una pregunta abierta al final)."
)
NO_TEXT_FALLBACK = (
    "No he podido darte una respuesta con texto en este turno — puede que "
    "la acción se haya denegado o cancelado a mitad de camino."
)
CONFIRM_TIMEOUT_S = 120
SAMPLE_RATE = 16000
VAD_FRAME_MS = 30
VAD_FRAME_SAMPLES = SAMPLE_RATE * VAD_FRAME_MS // 1000  # 480
_YES_RE = re.compile(r"^\s*(s(í|i)|claro|vale|yes|ok)\b", re.IGNORECASE)


def normalize_gain(pcm: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
    """Boosts a quiet recording up to a consistent loudness before it
    ever reaches Whisper. The Bluetooth mic's volume swings a lot
    between presses — peaks measured anywhere from ~11% to ~30% of full
    scale across otherwise identical presses (found live, by Rubén,
    2026-09-10) — and a quiet clip is a real, separate cause of bad
    transcriptions from anything VAD-related. Never boosts an
    already-loud clip (scale is clamped to 1.0 minimum), so this can
    only help, never introduce clipping that wasn't there before."""
    if pcm.size == 0:
        return pcm
    peak = int(np.abs(pcm).max())
    if peak == 0:
        return pcm
    scale = max(1.0, (target_peak * 32767) / peak)
    if scale == 1.0:
        return pcm
    boosted = pcm.astype(np.float32) * scale
    return np.clip(boosted, -32768, 32767).astype(np.int16)


def trim_to_speech(pcm: np.ndarray, aggressiveness: int = 2) -> np.ndarray:
    """Cuts leading/trailing silence (and drops a recording that's
    silence throughout) with webrtcvad, so Whisper only ever sees the
    part of the clip that actually sounds like speech — a browser
    MediaRecorder blob had no such trim, silence and background noise
    included, and that was a real source of bad transcriptions (found
    live, by Rubén, 2026-09-10, comparing against how backtalk captures
    audio). ~90ms of padding is kept on each side so a soft consonant
    at the very start/end of speech doesn't get clipped."""
    vad = webrtcvad.Vad(aggressiveness)
    n = len(pcm) // VAD_FRAME_SAMPLES
    if n == 0:
        return np.zeros(0, dtype=np.int16)
    is_speech = [
        vad.is_speech(pcm[i * VAD_FRAME_SAMPLES:(i + 1) * VAD_FRAME_SAMPLES].tobytes(), SAMPLE_RATE)
        for i in range(n)
    ]
    if not any(is_speech):
        return np.zeros(0, dtype=np.int16)
    first = is_speech.index(True)
    last = len(is_speech) - 1 - is_speech[::-1].index(True)
    pad = 3
    start = max(0, first - pad) * VAD_FRAME_SAMPLES
    end = min(len(pcm), (last + 1 + pad) * VAD_FRAME_SAMPLES)
    return pcm[start:end]


class Bridge:
    """One persistent SDK session per server process — a single-user
    assistant, same assumption backtalk makes. Also owns the STT/TTS
    engines (loaded once at boot, see start()) and the small event log
    that GET /events polls — the only "connection" any client has to
    this bridge is asking it questions."""

    def __init__(self, home_dir: Path):
        self.home_dir = home_dir
        self._client: ClaudeSDKClient | None = None
        self._pending_confirms: dict[str, asyncio.Future] = {}
        # FIFO, not a single id: Claude can (and does, every session
        # start, per CLAUDE.md's "read the vault index, then the latest
        # daily note") fire two tool calls in parallel, each hitting the
        # gate before either is answered. A single scalar here silently
        # lost the first one, found live (2026-09-10) when a "sí" only
        # ever resolved whichever question arrived last.
        self._confirm_queue: list[str] = []
        self._mode = "rest"
        self._events: list[dict] = []
        self._event_ids = itertools.count(1)
        # ask() can legitimately be in flight while a confirm answer comes
        # in — but TWO ask() calls sharing the one persistent SDK client
        # at once would interleave their messages. This keeps turns
        # serialized without blocking confirm resolution, which never
        # touches the client.
        self._turn_lock = asyncio.Lock()
        # Native mic capture (sounddevice), not the browser's
        # MediaRecorder — same technique backtalk uses, own code against
        # the same public library. One recording at a time, same
        # single-user assumption as everything else here.
        self._record_stream: sd.InputStream | None = None
        self._recording_frames: list[np.ndarray] | None = None
        # The CURRENT turn's audio, as a live stream — never embedded in
        # the polled JSON (a base64 WAV there once blocked the face's own
        # render loop long enough to freeze/stutter the tetraedro, found
        # live 2026-09-10) and, since the 2026-09-10 streaming rewrite,
        # never even fully buffered before the browser can hear it: see
        # stream_speak() / handle_audio_stream.
        self._audio_stream_queue: asyncio.Queue | None = None
        cfg = VoiceConfig.load(VOICE_CONFIG_PATH)
        self._stt = stt_engine(cfg.stt_engine, **cfg.stt_options)
        self._tts = tts_engine(cfg.tts_engine, **cfg.tts_options)
        # The Fase 1 language answer, written to language.json in the
        # Fase 3 "Identidad" step. Without it, Whisper re-guesses the
        # language on every short clip independently — on noisy audio
        # (a Bluetooth headset mic, say) that guess flips, and a real
        # Spanish sentence comes back transcribed as unrelated English
        # (found live, by Rubén, 2026-09-10: he said "¿qué puedes
        # hacer?", it heard "Thank you"). Pinning the language this
        # install was set up in removes that whole failure mode.
        try:
            self._language = json.loads(
                LANGUAGE_PATH.read_text(encoding="utf-8")
            ).get("code") or None
        except (OSError, json.JSONDecodeError):
            self._language = None
        # Fase 2's Permisos answer, written to permissions.json in the
        # Fase 3 "Identidad" step. Missing file = the safer default:
        # confirm before acting, same as an unanswered question would.
        try:
            self._confirm_before_action = json.loads(
                PERMISSIONS_PATH.read_text(encoding="utf-8")
            ).get("confirm_before_action", True)
        except (OSError, json.JSONDecodeError):
            self._confirm_before_action = True

    async def start(self):
        options = ClaudeAgentOptions(
            cwd=str(self.home_dir),
            system_prompt={"type": "preset", "preset": "claude_code"},
            permission_mode="default",
            can_use_tool=self._gate,
            # StreamEvent deltas, not just complete messages -- needed to
            # speak sentence-by-sentence as they're generated instead of
            # waiting for the whole reply (see ask_stream()).
            include_partial_messages=True,
        )
        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()

        # Load the voice engines HERE, on the main thread, at boot — not
        # lazily on first use inside run_in_executor(). Found live
        # (2026-09-10): building Kokoro's pipeline from a worker thread
        # hangs outright (no CPU, no network, no exception — just stuck),
        # almost certainly a main-thread requirement somewhere in its
        # espeak/phonemizer stack. Blocking startup once for this is a
        # fair trade for every real turn afterward never hitting it.
        print("[bridge] warming up voice engines...", flush=True)
        self._stt._load()
        self._tts._pipeline_for(self._tts._default_voice)
        print("[bridge] voice engines ready", flush=True)

    async def stop(self):
        if self._record_stream is not None:
            self._record_stream.stop()
            self._record_stream.close()
            self._record_stream = None
        if self._client:
            await self._client.disconnect()
            self._client = None
        self._stt.unload()
        self._tts.unload()

    # ---- the event log: every client polls this, nobody "connects" ----
    def _emit(self, event_type: str, **fields) -> dict:
        event = {"id": next(self._event_ids), "type": event_type, **fields}
        self._events.append(event)
        # unbounded growth would eventually matter on a Pi; nothing needs
        # more than a few minutes of scrollback
        if len(self._events) > 300:
            self._events = self._events[-300:]
        return event

    def events_since(self, since_id: int) -> list[dict]:
        return [e for e in self._events if e["id"] > since_id]

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._emit("state", value=mode)

    @property
    def awaiting_confirm_id(self) -> str | None:
        """The OLDEST unanswered confirmation, if any — answers resolve
        in the order the questions were asked."""
        return self._confirm_queue[0] if self._confirm_queue else None

    async def _gate(self, tool, tool_input, ctx):
        """Every tool use passes through here. Whether it actually stops
        to ask depends on the Fase 2 Permisos answer (permissions.json) —
        "confirm before every action" is the strictest reading of that
        choice: not just the destructive actions, all of them."""
        if not self._confirm_before_action:
            return PermissionResultAllow(behavior="allow")
        confirm_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_confirms[confirm_id] = fut
        self._confirm_queue.append(confirm_id)
        what = f"usar {tool}"
        if isinstance(tool_input, dict) and tool_input.get("command"):
            what = f"ejecutar: {tool_input['command'][:200]}"
        elif isinstance(tool_input, dict) and tool_input.get("file_path"):
            what = f"tocar el archivo {tool_input['file_path']}"
        # NOT "id": that key already means the event log's own monotonic
        # id inside _emit() -- collided with it here once, silently
        # corrupting it to this UUID string and breaking every poll's
        # since-comparison from that point on (found testing, 2026-09-10)
        self._emit("confirm_request", confirm_id=confirm_id, question=f"¿Puedo {what}? Responde sí o no.")
        try:
            approved = await asyncio.wait_for(fut, CONFIRM_TIMEOUT_S)
        except asyncio.TimeoutError:
            self._pending_confirms.pop(confirm_id, None)
            if confirm_id in self._confirm_queue:
                self._confirm_queue.remove(confirm_id)
            return PermissionResultDeny(
                behavior="deny",
                message="No hubo respuesta a tiempo; la acción no se aprobó.",
                interrupt=False,
            )
        if approved:
            return PermissionResultAllow(behavior="allow")
        return PermissionResultDeny(behavior="deny", message="Denegado por la persona.", interrupt=False)

    def resolve_confirm(self, confirm_id: str, approved: bool):
        if confirm_id in self._confirm_queue:
            self._confirm_queue.remove(confirm_id)
        fut = self._pending_confirms.pop(confirm_id, None)
        if fut and not fut.done():
            fut.set_result(approved)

    async def ask_stream(self, text: str):
        """Yields each sentence AS SOON AS Claude finishes it, instead of
        the whole reply at once — the fix for the ~1-minute turnaround
        Rubén found (2026-09-10): waiting for the full reply, then
        synthesizing the full reply, then sending it, means every one of
        those steps' latency stacks up in series. Streaming sentence by
        sentence means synthesis of sentence 1 starts while Claude is
        still writing sentence 2 — the same technique backtalk uses
        (brain.py's ask_stream), rebuilt here from scratch against the
        same public SDK, no code shared."""
        self.set_mode("thinking")
        sentence_end = re.compile(r"(?<=[.!?])\s")
        async with self._turn_lock:
            await self._client.query(text)
            buf = ""
            spoke_yet = False
            async for msg in self._client.receive_response():
                t = type(msg).__name__
                if t == "StreamEvent":
                    ev = getattr(msg, "event", {}) or {}
                    if ev.get("type") == "content_block_delta":
                        delta = ev.get("delta", {}) or {}
                        if delta.get("type") == "text_delta":
                            buf += delta.get("text", "")
                            while True:
                                m = sentence_end.search(buf)
                                if not m:
                                    break
                                sentence, buf = buf[:m.end()].strip(), buf[m.end():]
                                if sentence:
                                    if not spoke_yet:
                                        self.set_mode("speaking")
                                        spoke_yet = True
                                    yield sentence
                    elif ev.get("type") == "content_block_stop":
                        tail = buf.strip()
                        buf = ""
                        if tail:
                            if not spoke_yet:
                                self.set_mode("speaking")
                                spoke_yet = True
                            yield tail
                elif t == "ResultMessage":
                    if getattr(msg, "is_error", False):
                        print(f"[bridge] turn ended with error: {msg!r:.300}", flush=True)
                    break
            tail = buf.strip()
            if tail:
                if not spoke_yet:
                    self.set_mode("speaking")
                yield tail

    def start_recording(self):
        """Opens the mic and starts buffering — stop_recording() does the
        actual VAD trim once the whole clip is in hand, so this stays
        cheap and can't glitch mid-capture.

        Callback-driven, NOT the blocking-read-on-a-thread shape
        ears.py's record_held() uses. That was tried (to match Jared's
        proven reference exactly) and caused a REAL production
        incident within minutes: a Bluetooth dropout leaves the
        thread's blocking .read() stuck, stop_recording()'s 2s join
        times out, and closing the stream out from under a still-
        blocked read spun the reader in a tight loop — 333% CPU,
        pegging the whole Pi (found live, by Rubén, 2026-09-10).
        Reverted to this, the shape that ran the entire rest of the day
        without incident, keeping only the explicit blocksize."""
        if self._record_stream is not None:
            return
        self._recording_frames = []

        def _callback(indata, frames, time_info, status):
            self._recording_frames.append(indata[:, 0].copy())

        self._record_stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16",
            blocksize=VAD_FRAME_SAMPLES, callback=_callback,
        )
        self._record_stream.start()

    def stop_recording(self, trim: bool = False) -> np.ndarray:
        """trim=False (push-to-talk's default) mirrors backtalk's
        record_held(): "the button is the VAD, no endpointing" — the
        person's own press/release already marks the start and end, so
        the raw capture goes to Whisper untouched. VAD trimming is only
        for "live" mode's blind fixed-length windows, which have no such
        marker and genuinely need the silence cut out. Trimming a
        deliberate PTT press was clipping real speech on a quiet
        Bluetooth signal (found live, by Rubén, 2026-09-10: the start or
        end of what he said kept going missing)."""
        if self._record_stream is None:
            return np.zeros(0, dtype=np.int16)
        self._record_stream.stop()
        self._record_stream.close()
        self._record_stream = None
        frames = self._recording_frames or []
        self._recording_frames = None
        if not frames:
            print("[bridge] stop_recording: no frames captured at all", flush=True)
            return np.zeros(0, dtype=np.int16)
        raw = np.concatenate(frames)
        rms = float(np.sqrt(np.mean(raw.astype(np.float64) ** 2))) if raw.size else 0.0
        peak = int(np.abs(raw).max()) if raw.size else 0
        result = trim_to_speech(raw) if trim else raw
        print(f"[bridge] stop_recording: {raw.size} samples, rms={rms:.1f}, peak={peak}/32768, "
              f"trim={trim}, using {result.size} samples", flush=True)
        return result

    async def transcribe(self, pcm: np.ndarray) -> str:
        if pcm.size == 0:
            return ""
        before = int(np.abs(pcm).max())
        pcm = normalize_gain(pcm)
        after = int(np.abs(pcm).max())
        if after != before:
            print(f"[bridge] gain boosted: peak {before} -> {after}/32768", flush=True)
        loop = asyncio.get_running_loop()
        audio_f32 = pcm.astype(np.float32) / 32768.0
        return await loop.run_in_executor(None, self._stt.transcribe, audio_f32, SAMPLE_RATE, self._language)

    async def stream_speak(self, text: str, queue: asyncio.Queue) -> None:
        """Pushes raw int16 PCM chunks onto queue AS Kokoro generates
        them — not after synthesis of a whole sentence-batch finishes.
        Real-time streaming, the step toward an actual live
        conversation (Rubén's goal, 2026-09-10): each chunk crosses
        into the event loop the moment it exists, so /audio_stream can
        write it to the browser essentially as it's spoken, instead of
        the whole clip waiting for `list(self._tts.synthesize(...))` to
        finish before ANY of it goes out."""
        if not text.strip():
            return
        loop = asyncio.get_running_loop()
        gen = self._tts.synthesize(text)
        while True:
            chunk = await loop.run_in_executor(None, lambda: next(gen, None))
            if chunk is None:
                break
            await queue.put(chunk.tobytes())

    async def voice_turn(self, pcm: np.ndarray):
        """The full voice pipeline for one recording: transcribe -> a
        confirm answer if one's pending, otherwise the same ask() a
        typed message goes through -> speak the reply back. The
        transcript is emitted too, so voice and chat share one visible
        transcript."""
        self.set_mode("thinking")
        transcript = await self.transcribe(pcm)

        if self.awaiting_confirm_id:
            confirm_id = self.awaiting_confirm_id
            approved = bool(_YES_RE.match(transcript.strip())) if transcript else False
            self._emit("user_transcript", text=transcript or "(sin entender)")
            self.resolve_confirm(confirm_id, approved)
            return

        if not transcript:
            self._emit("assistant", text="No te he oído bien — ¿lo repites?")
            self.set_mode("rest")
            return
        self._emit("user_transcript", text=transcript)
        await self._answer(transcript, via_voice=True)

    async def chat_turn(self, text: str):
        if self.awaiting_confirm_id:
            confirm_id = self.awaiting_confirm_id
            approved = bool(_YES_RE.match(text.strip()))
            self.resolve_confirm(confirm_id, approved)
            return
        await self._answer(text, via_voice=False)

    async def _answer(self, text: str, via_voice: bool = False):
        """Speaks and shows text as soon as Claude finishes each sentence
        — NOT the whole reply at once. 'assistant_chunk' events append to
        the same chat bubble client-side; a bare 'assistant' event only
        happens for the empty-reply fallback, a genuine one-shot message.

        Real-time audio streaming (2026-09-10, replacing WAV-over-HTTP):
        a fresh asyncio.Queue is opened as THE stream for this turn — the
        face is expected to already be reading /audio_stream by the time
        this runs (it opens that fetch right after submitting the voice
        turn, before waiting on any poll). Chunks land in the queue as
        Kokoro produces them (stream_speak), sentence by sentence, with
        no batching: the WAV-batching-for-smoothness compromise doesn't
        apply here since real streaming has no per-clip HTTP/decode seam
        to smooth over in the first place. Typed chat never opens a
        queue — text stays silent, same as before.

        via_voice tags what's actually SENT to Claude (never the
        displayed transcript) with a short marker — otherwise a spoken
        turn looks identical to a typed one on Claude's side, and asking
        "¿me estás escuchando?" out loud got answered as if nothing had
        been heard at all (found live, by Rubén, 2026-09-10)."""
        prompt = (
            f"[Te acaba de hablar por voz, no escribir. Responde breve, como en una "
            f"conversación real — dos o tres frases, no una charla entera; si hace falta "
            f"más detalle, dilo y ofrece seguir por texto] {text}"
        ) if via_voice else text
        queue: asyncio.Queue | None = None
        if via_voice:
            queue = asyncio.Queue()
            self._audio_stream_queue = queue
            self._emit("audio_stream", sample_rate=self._tts.sample_rate)
        said_anything = False
        async for sentence in self.ask_stream(prompt):
            said_anything = True
            self._emit("assistant_chunk", text=sentence)
            if queue is not None:
                await self.stream_speak(sentence, queue)
        if queue is not None:
            await queue.put(None)  # tells /audio_stream this turn is done
        if not said_anything:
            self._emit("assistant", text=NO_TEXT_FALLBACK)
        self.set_mode("rest")


async def handle_events(request: web.Request):
    bridge: Bridge = request.app["bridge"]
    since = int(request.query.get("since", 0))
    return web.json_response({
        "mode": bridge._mode,
        "events": bridge.events_since(since),
    })


async def handle_audio_stream(request: web.Request):
    """Raw int16 PCM, mono, streamed live as the CURRENT turn's queue
    fills — no WAV container (that needs a byte count up front, which a
    live stream doesn't have) and no wait for the whole reply. The face
    opens this immediately after submitting a voice turn, before the
    turn has even started answering; whatever's in the queue by the
    time this connects is exactly what it plays, in order."""
    bridge: Bridge = request.app["bridge"]
    resp = web.StreamResponse(headers={"Content-Type": "application/octet-stream"})
    await resp.prepare(request)
    # The face opens this the instant it submits a voice turn — often
    # microseconds before _answer() has actually created this turn's
    # queue. Give it a moment to show up rather than closing empty.
    queue = bridge._audio_stream_queue
    waited = 0.0
    while queue is None and waited < 3.0:
        await asyncio.sleep(0.03)
        waited += 0.03
        queue = bridge._audio_stream_queue
    if queue is not None:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            try:
                await resp.write(chunk)
            except (ConnectionResetError, ConnectionError):
                break
    await resp.write_eof()
    return resp


async def handle_voice_start(request: web.Request):
    bridge: Bridge = request.app["bridge"]
    bridge.start_recording()
    bridge.set_mode("listening")
    return web.json_response({"ok": True})


async def handle_voice_stop(request: web.Request):
    bridge: Bridge = request.app["bridge"]
    trim = request.query.get("trim") == "1"
    pcm = bridge.stop_recording(trim=trim)
    asyncio.create_task(_run_safely(bridge, bridge.voice_turn(pcm)))
    return web.json_response({"ok": True}, status=202)


async def handle_chat(request: web.Request):
    bridge: Bridge = request.app["bridge"]
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)
    if data.get("type") == "greet":
        text = GREETING_PROMPT
    else:
        text = (data.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False}, status=400)
    asyncio.create_task(_run_safely(bridge, bridge.chat_turn(text)))
    return web.json_response({"ok": True}, status=202)


async def _run_safely(bridge: Bridge, coro):
    """A turn running as a background task (POST returns before it's
    done — the result shows up via /events) must never vanish silently
    on error."""
    try:
        await coro
    except Exception as e:
        bridge._emit("error", text=str(e)[:300])
        bridge.set_mode("rest")


async def make_app():
    app = web.Application()
    bridge = Bridge(HOME_DIR)
    await bridge.start()
    app["bridge"] = bridge
    app.router.add_get("/events", handle_events)
    app.router.add_get("/audio_stream", handle_audio_stream)
    app.router.add_post("/voice/start", handle_voice_start)
    app.router.add_post("/voice/stop", handle_voice_stop)
    app.router.add_post("/chat", handle_chat)
    app.router.add_static("/", FACE_DIR, show_index=False)

    async def on_cleanup(app):
        await bridge.stop()
    app.on_cleanup.append(on_cleanup)

    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=PORT)
