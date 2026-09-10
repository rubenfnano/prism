"""PRISM: the bridge (Fase 4).

Runs INSIDE the voice piece's own venv (see voice/pyproject.toml) —
avoids installing torch/whisper in two separate environments. Serves the
face over HTTP, opens a WebSocket for real-time chat, and drives a
persistent Claude Agent SDK session whose cwd is the assistant's home
folder — whatever CLAUDE.md lives there is who is answering.

First scope (2026-09-10): typed chat only. Voice (mic capture, STT/TTS
wired to real turns) is the next round — logVoiceTurn() in the face is
still the demo for now, only the chat panel talks to this server.

Permission handling mirrors backtalk's spoken gate (brain.py /
make_permission_gate in main.py), but the question travels over the
WebSocket as a chat bubble instead of being spoken, and the answer is
the next chat message instead of a spoken yes/no.
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from aiohttp import web, WSMsgType
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
)

HOME_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
FACE_DIR = HOME_DIR / "cara"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8793

GREETING_PROMPT = (
    "Preséntate con tu saludo inicial de sesión, tal como manda tu propio "
    "CLAUDE.md (breve, distinto cada vez, con una pregunta abierta al final)."
)
CONFIRM_TIMEOUT_S = 120


class Bridge:
    """One persistent SDK session per server process — a single-user
    assistant, same assumption backtalk makes."""

    def __init__(self, home_dir: Path):
        self.home_dir = home_dir
        self._client: ClaudeSDKClient | None = None
        self._pending_confirms: dict[str, asyncio.Future] = {}
        self._ws: web.WebSocketResponse | None = None

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

    def attach(self, ws: web.WebSocketResponse):
        self._ws = ws

    async def _send(self, payload: dict):
        if self._ws is not None:
            await self._ws.send_str(json.dumps(payload))

    async def _gate(self, tool, tool_input, ctx):
        """Every tool use pauses here — Rubén chose "confirm before every
        action" in the Fase 2 interview, so this is the strictest gate,
        not just the destructive-action one."""
        confirm_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_confirms[confirm_id] = fut
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
        fut = self._pending_confirms.pop(confirm_id, None)
        if fut and not fut.done():
            fut.set_result(approved)

    async def ask(self, text: str) -> str:
        await self._send({"type": "state", "value": "thinking"})
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
                break
        await self._send({"type": "state", "value": "speaking"})
        reply = "".join(pieces).strip() or "..."
        await self._send({"type": "state", "value": "rest"})
        return reply


async def handle_ws(request: web.Request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    bridge: Bridge = request.app["bridge"]
    bridge.attach(ws)

    async for msg in ws:
        if msg.type != WSMsgType.TEXT:
            continue
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            continue

        if data.get("type") == "chat":
            text = (data.get("text") or "").strip()
            if not text:
                continue
            try:
                reply = await bridge.ask(text)
                await ws.send_str(json.dumps({"type": "assistant", "text": reply}))
            except Exception as e:  # a broken turn must never kill the socket
                await ws.send_str(json.dumps({"type": "error", "text": str(e)[:300]}))

        elif data.get("type") == "greet":
            try:
                reply = await bridge.ask(GREETING_PROMPT)
                await ws.send_str(json.dumps({"type": "assistant", "text": reply}))
            except Exception as e:
                await ws.send_str(json.dumps({"type": "error", "text": str(e)[:300]}))

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
