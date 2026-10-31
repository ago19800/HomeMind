"""
ha_client/websocket_client.py
Uses websocket-client (sync wrapped in thread) to avoid asyncio timeout issues
with the HA Supervisor proxy.
"""
import asyncio
import json
import logging
import os
import threading
import time
from typing import Callable
from collections import defaultdict

logger = logging.getLogger("homemind.ws")


class HAWebSocketClient:
    def __init__(self, token: str):
        self.url = os.getenv("HA_WS_URL", "ws://supervisor/core/websocket")
        self.token = token
        self._ws = None
        self._msg_id = 1
        self._id_lock = threading.Lock()
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._pending: dict[int, asyncio.Future] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = False

    def on_event(self, event_type: str, handler: Callable):
        self._handlers[event_type].append(handler)

    async def call_service(self, domain: str, service: str, data: dict = None) -> dict:
        return await self._send({
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": data or {},
        })

    async def subscribe_events(self, event_type: str = "state_changed"):
        await self._send({"type": "subscribe_events", "event_type": event_type})
        logger.info(f"Subscribed to: {event_type}")

    async def connect_and_run(self):
        """Main loop — reconnects forever using websockets with short timeouts."""
        import websockets.sync.client as ws_sync
        import time as _t
        self._loop = asyncio.get_event_loop()
        _fail_count  = 0   # disconnessioni consecutive
        _last_ok_log = 0   # timestamp ultimo log "Connecting"

        while True:
            try:
                now = _t.time()
                # Log solo alla prima connessione o dopo 5+ min di silenzio
                if _fail_count == 0 or (now - _last_ok_log) > 300:
                    logger.info(f"Connecting to {self.url}")
                    _last_ok_log = now

                await asyncio.to_thread(self._sync_session, ws_sync)
                _fail_count = 0  # connessione riuscita

            except Exception as e:
                _fail_count += 1
                # Loga solo alla prima disconnessione o ogni 5 tentativi
                if _fail_count == 1:
                    logger.warning(f"WebSocket disconnesso: {type(e).__name__}: {e}")
                elif _fail_count % 5 == 0:
                    logger.warning(f"WebSocket: {_fail_count} disconnessioni consecutive")

            self._connected = False
            # Backoff progressivo: 5s → 5s → 10s → 10s → 30s
            delay = 5 if _fail_count <= 2 else (10 if _fail_count <= 4 else 30)
            await asyncio.sleep(delay)

    def _sync_session(self, ws_sync):
        """Runs in a thread. Connects, authenticates, sends pings, dispatches events."""
        with ws_sync.connect(
            self.url,
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            self._ws = ws
            # Auth handshake
            msg = json.loads(ws.recv())
            assert msg["type"] == "auth_required"
            ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            resp = json.loads(ws.recv())
            if resp["type"] != "auth_ok":
                raise ConnectionError(f"Auth failed: {resp}")

            ha_version = resp.get("ha_version", "?")
            self._connected = True
            # Schedule async log from sync thread
            self._loop.call_soon_threadsafe(
                logger.info, f"Authenticated. HA version: {ha_version}"
            )

            # Subscribe to events
            sub_id = self._next_id()
            ws.send(json.dumps({"id": sub_id, "type": "subscribe_events",
                                "event_type": "state_changed"}))
            ws.recv()  # consume subscription ack
            self._loop.call_soon_threadsafe(
                logger.info, "Subscribed to event: state_changed"
            )

            # Main receive + ping loop
            ws.socket.settimeout(10)   # recv times out after 10s → send ping
            while True:
                try:
                    raw = ws.recv()
                    self._dispatch(raw)
                except TimeoutError:
                    # Send HA-level ping to keep proxy alive
                    ping_id = self._next_id()
                    ws.send(json.dumps({"id": ping_id, "type": "ping"}))
                    try:
                        pong = json.loads(ws.recv())
                        logger.debug(f"HA ping OK → {pong.get('type')}")
                    except Exception:
                        break   # reconnect

    def _next_id(self) -> int:
        with self._id_lock:
            mid = self._msg_id
            self._msg_id += 1
        return mid

    def _dispatch(self, raw: str):
        try:
            msg = json.loads(raw)
        except Exception:
            return

        msg_id = msg.get("id")
        # Resolve pending async futures
        if msg_id and msg_id in self._pending:
            future = self._pending.pop(msg_id)
            self._loop.call_soon_threadsafe(future.set_result, msg)
            return

        # Dispatch events to async handlers
        if msg.get("type") == "event":
            event = msg.get("event", {})
            etype = event.get("event_type", "")
            for handler in self._handlers.get(etype, []):
                asyncio.run_coroutine_threadsafe(handler(event), self._loop)

    async def _send(self, payload: dict) -> dict:
        if not self._ws or not self._connected:
            raise RuntimeError("WebSocket not connected")
        msg_id = self._next_id()
        payload["id"] = msg_id
        future: asyncio.Future = self._loop.create_future()
        self._pending[msg_id] = future
        self._ws.send(json.dumps(payload))
        return await asyncio.wait_for(future, timeout=15)
