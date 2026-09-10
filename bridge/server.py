"""PRISM: the bridge (Fase 4).

Runs INSIDE the voice piece's own venv (see voice/pyproject.toml) —
avoids installing torch/whisper in two separate environments. Serves the
face over HTTP, opens a WebSocket for real-time chat AND voice, and
drives a persistent Claude Agent SDK session whose cwd is the
assistant's home folder — whatever CLAUDE.md lives there is who is
answering.

Voice turns arrive as a single BINARY WebSocket frame (the browser's
whole recording, whatever container MediaRecorder used — webm/opus in
Chromium) once push-to-talk is released, or every few seconds while
"live" mode cycles. Decoded with PyAV (already a faster-whisper
dependency) straight to 16kHz mono float32, so voice/engines never see
anything but the numpy array they were designed for.

Permission handling mirrors backtalk's spoken gate (brain.py /
make_permission_gate in main.py), but the question travels over the
WebSocket as a chat bubble instead of being spoken, and the answer is
the next chat message instead of a spoken yes/no.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import sys
import uuid
import wave
from pathlib import Path

import numpy as np
from aiohttp import web, WSMsgType
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
    engines (lazy-loaded, per voice.json) — this process already pays
    the torch/whisper import cost, no reason to load it twice."""

    def __init__(self, home_dir: Path):
        self.home_dir = home_dir
        self._client: ClaudeSDKClient | None = None
        self._pending_confirms: dict[str, asyncio.Future] = {}
        self._awaiting_confirm_id: str | None = None
        self._ws: web.WebSocketResponse | None = None
        # ask() can legitimately be in flight while a confirm answer comes
        # in (that's the whole point of the fix above) — but TWO ask()
        # calls sharing the one persistent SDK client at once would
        # interleave their messages. This keeps turns serialized without
        # blocking confirm resolution, which never touches the client.
        self._turn_lock = asyncio.Lock()
        cfg = VoiceConfig.load(VOICE_CONFIG_PATH)
        self._stt = stt_engine(cfg.stt_engine, **cfg.stt_options)
        self._tts = tts_engine(cfg.tts_engine, **cfg.tts_options)
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
        )
        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()

    async def stop(self):
        if self._client:
            await self._client.disconnect()
            self._client = None
        self._stt.unload()
        self._tts.unload()

    def attach(self, ws: web.WebSocketResponse):
        self._ws = ws

    async def _send(self, payload: dict):
        """The browser can close mid-turn (a page reload, a lost wifi
        connection on the Pi) — a dropped socket must never crash the
        turn or the server, it just means nobody heard the answer."""
        if self._ws is None or self._ws.closed:
            return
        try:
            await self._ws.send_str(json.dumps(payload))
        except (ConnectionResetError, ConnectionError):
            pass

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
        # tracked so a VOICE turn (not just typed chat) can answer this —
        # single pending confirm at a time, same single-user assumption
        # as the rest of the bridge
        self._awaiting_confirm_id = confirm_id
        what = f"usar {tool}"
        if isinstance(tool_input, dict) and tool_input.get("command"):
            what = f"ejecutar: {tool_input['command'][:200]}"
        elif isinstance(tool_input, dict) and tool_input.get("file_path"):
            what = f"tocar el archivo {tool_input['file_path']}"
        await self._send({
            "type": "confirm_request",
            "id": confirm_id,
            "question": f"¿Puedo {what}? Responde sí o no.",
        })
        try:
            approved = await asyncio.wait_for(fut, CONFIRM_TIMEOUT_S)
        except asyncio.TimeoutError:
            self._pending_confirms.pop(confirm_id, None)
            if self._awaiting_confirm_id == confirm_id:
                self._awaiting_confirm_id = None
            return PermissionResultDeny(
                behavior="deny",
                message="No hubo respuesta a tiempo; la acción no se aprobó.",
                interrupt=False,
            )
        if approved:
            return PermissionResultAllow(behavior="allow")
        return PermissionResultDeny(
            behavior="deny",
            message="Denegado por la persona.",
            interrupt=False,
        )

    def resolve_confirm(self, confirm_id: str, approved: bool):
        if self._awaiting_confirm_id == confirm_id:
            self._awaiting_confirm_id = None
        fut = self._pending_confirms.pop(confirm_id, None)
        if fut and not fut.done():
            fut.set_result(approved)

    async def ask(self, text: str) -> str:
        """One full turn with Claude Code. If the turn ends without any
        text block — a denied/timed-out confirmation with nothing left
        to say, or a tool-only reply — NO_TEXT_FALLBACK explains that
        honestly instead of a bare, confusing "..."."""
        await self._send({"type": "state", "value": "thinking"})
        async with self._turn_lock:
            await self._client.query(text)
            pieces = []
            async for msg in self._client.receive_response():
                t = type(msg).__name__
                if t == "AssistantMessage":
                    for block in getattr(msg, "content", []) or []:
                        txt = getattr(block, "text", None)
                        if txt:
                            pieces.append(txt)
                elif t == "ResultMessage":
                    if getattr(msg, "is_error", False):
                        print(f"[bridge] turn ended with error: {msg!r:.300}", flush=True)
                    break
        await self._send({"type": "state", "value": "speaking"})
        reply = "".join(pieces).strip() or NO_TEXT_FALLBACK
        await self._send({"type": "state", "value": "rest"})
        return reply

    async def transcribe(self, audio_bytes: bytes) -> str:
        loop = asyncio.get_running_loop()
        pcm, rate = await loop.run_in_executor(None, decode_audio, audio_bytes)
        if pcm.size == 0:
            return ""
        return await loop.run_in_executor(None, self._stt.transcribe, pcm, rate)

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

    async def voice_confirm_turn(self, audio_bytes: bytes):
        """A permission question is waiting for an answer — a PTT/live
        recording right now means "sí" or "no", not a new question.
        Without this, the question only ever showed in the chat panel,
        which isn't even on screen in ptt/live mode: the gate would sit
        there for the full CONFIRM_TIMEOUT_S with no way to answer it by
        voice at all (found live, by Rubén, on 2026-09-10)."""
        confirm_id = self._awaiting_confirm_id
        await self._send({"type": "state", "value": "thinking"})
        transcript = await self.transcribe(audio_bytes)
        if not confirm_id or confirm_id not in self._pending_confirms:
            # answered or timed out while transcribing — fall through to
            # a normal turn instead of silently dropping what was said
            await self._send({"type": "state", "value": "rest"})
            if transcript:
                await self.voice_turn_from_transcript(transcript)
            return
        approved = bool(_YES_RE.match(transcript.strip())) if transcript else False
        await self._send({"type": "user_transcript", "text": transcript or "(sin entender)"})
        self.resolve_confirm(confirm_id, approved)

    async def voice_turn(self, audio_bytes: bytes):
        """The full voice pipeline for one recording: transcribe -> the
        same ask() a typed message goes through -> speak the reply back.
        The transcript is sent to the browser too, so voice and chat
        share one transcript (the same design the face already had for
        its demo turns) — it's just real now."""
        if self._awaiting_confirm_id:
            await self.voice_confirm_turn(audio_bytes)
            return
        await self._send({"type": "state", "value": "thinking"})
        transcript = await self.transcribe(audio_bytes)
        await self.voice_turn_from_transcript(transcript)

    async def voice_turn_from_transcript(self, transcript: str):
        if not transcript:
            await self._send({
                "type": "assistant",
                "text": "No te he oído bien — ¿lo repites?",
            })
            await self._send({"type": "state", "value": "rest"})
            return
        await self._send({"type": "user_transcript", "text": transcript})
        reply = await self.ask(transcript)
        await self._send({"type": "assistant", "text": reply})
        audio_b64 = await self.synthesize(reply)
        if audio_b64:
            await self._send({
                "type": "audio",
                "data": audio_b64,
                "sample_rate": self._tts.sample_rate,
            })
        else:
            await self._send({"type": "state", "value": "rest"})


async def _run_voice_turn(bridge: "Bridge", audio_bytes: bytes):
    try:
        await bridge.voice_turn(audio_bytes)
    except Exception as e:  # a broken turn must never kill the socket
        await bridge._send({"type": "error", "text": str(e)[:300]})


async def _run_chat_turn(bridge: "Bridge", text: str):
    try:
        reply = await bridge.ask(text)
        await bridge._send({"type": "assistant", "text": reply})
    except Exception as e:
        await bridge._send({"type": "error", "text": str(e)[:300]})


async def handle_ws(request: web.Request):
    ws = web.WebSocketResponse(max_msg_size=20 * 1024 * 1024)
    await ws.prepare(request)
    bridge: Bridge = request.app["bridge"]
    bridge.attach(ws)

    # EVERY turn runs as its OWN task, never awaited inline here. A turn
    # can take a minute or more (cold model loads, a permission question
    # waiting on a person) — if this loop awaited it directly, no other
    # frame on this same connection could be received meanwhile, which is
    # exactly what silently deadlocked "answer by voice" against its own
    # permission question (found live, by Rubén, on 2026-09-10): the
    # gate's answer IS the next frame, and the loop couldn't reach it.
    async for msg in ws:
        if msg.type == WSMsgType.BINARY:
            asyncio.create_task(_run_voice_turn(bridge, msg.data))
            continue

        if msg.type != WSMsgType.TEXT:
            continue
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            continue

        if data.get("type") in ("chat", "greet"):
            text = GREETING_PROMPT if data["type"] == "greet" else (data.get("text") or "").strip()
            if text:
                asyncio.create_task(_run_chat_turn(bridge, text))

        elif data.get("type") == "confirm":
            bridge.resolve_confirm(data.get("id"), bool(data.get("approved")))

    return ws


async def make_app():
    app = web.Application()
    bridge = Bridge(HOME_DIR)
    await bridge.start()
    app["bridge"] = bridge
    app.router.add_get("/ws", handle_ws)
    app.router.add_static("/", FACE_DIR, show_index=False)

    async def on_cleanup(app):
        await bridge.stop()
    app.on_cleanup.append(on_cleanup)

    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=PORT)
