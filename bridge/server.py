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
  POST /voice   (binary body: whatever MediaRecorder produced)
                             one recorded turn. Returns immediately
                             (202) — the real work happens in the
                             background and shows up via /events.
  POST /chat    ({"text": "..."} or {"type": "greet"})
                             same as above, for typed turns.
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
import base64
import io
import itertools
import json
import re
import sys
import uuid
import wave
from pathlib import Path

import numpy as np
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
SPEAK_BATCH_CHARS = 80  # synthesize roughly this many characters at a time
WHISPER_SAMPLE_RATE = 16000
_YES_RE = re.compile(r"^\s*(s(í|i)|claro|vale|yes|ok)\b", re.IGNORECASE)


def decode_audio(data: bytes) -> tuple[np.ndarray, int]:
    """Whatever container the browser recorded (webm/opus in practice) ->
    16kHz mono float32, decoded with PyAV so no extra dependency (or a
    system ffmpeg binary) is needed beyond what faster-whisper already
    installs."""
    import av

    container = av.open(io.BytesIO(data))
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=WHISPER_SAMPLE_RATE)
    chunks = []
    stream = container.streams.audio[0]
    for frame in container.decode(stream):
        frame.pts = None
        for rframe in resampler.resample(frame):
            chunks.append(rframe.to_ndarray())
    container.close()
    if not chunks:
        return np.zeros(0, dtype=np.float32), WHISPER_SAMPLE_RATE
    return np.concatenate(chunks, axis=1).flatten().astype(np.float32), WHISPER_SAMPLE_RATE


def pcm_to_wav_b64(chunks: list[np.ndarray], sample_rate: int) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        for chunk in chunks:
            wf.writeframes(chunk.tobytes())
    return base64.b64encode(buf.getvalue()).decode("ascii")


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
        if self._client:
            await self._client.disconnect()
            self._client = None
        self._stt.unload()
        self._tts.unload()

    # ---- the event log: every client polls this, nobody "connects" ----
    def _emit(self, event_type: str, **fields) -> None:
        self._events.append({"id": next(self._event_ids), "type": event_type, **fields})
        # unbounded growth would eventually matter on a Pi; nothing needs
        # more than a few minutes of scrollback
        if len(self._events) > 300:
            self._events = self._events[-300:]

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

    async def transcribe(self, audio_bytes: bytes) -> str:
        loop = asyncio.get_running_loop()
        pcm, rate = await loop.run_in_executor(None, decode_audio, audio_bytes)
        if pcm.size == 0:
            return ""
        return await loop.run_in_executor(None, self._stt.transcribe, pcm, rate, self._language)

    async def synthesize(self, text: str) -> str | None:
        """Returns a base64 WAV, or None if there's nothing worth saying
        (an empty reply shouldn't play silence)."""
        if not text.strip():
            return None
        loop = asyncio.get_running_loop()

        def _run():
            chunks = list(self._tts.synthesize(text))
            return pcm_to_wav_b64(chunks, self._tts.sample_rate)

        return await loop.run_in_executor(None, _run)

    async def voice_turn(self, audio_bytes: bytes):
        """The full voice pipeline for one recording: transcribe -> a
        confirm answer if one's pending, otherwise the same ask() a
        typed message goes through -> speak the reply back. The
        transcript is emitted too, so voice and chat share one visible
        transcript."""
        self.set_mode("thinking")
        transcript = await self.transcribe(audio_bytes)

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
        await self._answer(transcript)

    async def chat_turn(self, text: str):
        if self.awaiting_confirm_id:
            confirm_id = self.awaiting_confirm_id
            approved = bool(_YES_RE.match(text.strip()))
            self.resolve_confirm(confirm_id, approved)
            return
        await self._answer(text)

    async def _answer(self, text: str):
        """Speaks and shows text as soon as Claude finishes each sentence
        — NOT the whole reply at once. 'assistant_chunk' events append to
        the same chat bubble client-side; a bare 'assistant' event only
        happens for the empty-reply fallback, a genuine one-shot message.

        Sentence-by-sentence TEXT, but AUDIO is batched a couple of
        sentences at a time (SPEAK_BATCH_CHARS) — one clip per single
        short sentence sounded choppy (found live, by Rubén,
        2026-09-10): every clip boundary is an audible seam, and short
        sentences meant a lot of them. Batching trades a little of the
        latency win for noticeably smoother speech."""
        said_anything = False
        audio_buf = ""
        async for sentence in self.ask_stream(text):
            said_anything = True
            self._emit("assistant_chunk", text=sentence)
            audio_buf = f"{audio_buf} {sentence}".strip()
            if len(audio_buf) >= SPEAK_BATCH_CHARS:
                audio_b64 = await self.synthesize(audio_buf)
                if audio_b64:
                    self._emit("audio", data=audio_b64, sample_rate=self._tts.sample_rate)
                audio_buf = ""
        if audio_buf:
            audio_b64 = await self.synthesize(audio_buf)
            if audio_b64:
                self._emit("audio", data=audio_b64, sample_rate=self._tts.sample_rate)
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


async def handle_voice(request: web.Request):
    bridge: Bridge = request.app["bridge"]
    audio_bytes = await request.read()
    asyncio.create_task(_run_safely(bridge, bridge.voice_turn(audio_bytes)))
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
    app.router.add_post("/voice", handle_voice)
    app.router.add_post("/chat", handle_chat)
    app.router.add_static("/", FACE_DIR, show_index=False)

    async def on_cleanup(app):
        await bridge.stop()
    app.on_cleanup.append(on_cleanup)

    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=PORT)
