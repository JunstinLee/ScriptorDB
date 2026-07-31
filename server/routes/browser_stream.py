from __future__ import annotations

import asyncio
import json
import time
from fractions import Fraction
from io import BytesIO

import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from PIL import Image

from browser import get_manager
from logging_setup import get_logger

logger = get_logger("browser_stream")

router = APIRouter(prefix="/api", tags=["browser_stream"])


class PlaywrightScreencastTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=2)
        self._timestamp = 0
        self._frame_count = 0

    def add_frame(self, jpeg_bytes: bytes):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._queue.put_nowait((jpeg_bytes, time.time()))

    async def recv(self) -> VideoFrame:
        jpeg_bytes, pts = await self._queue.get()

        img = Image.open(BytesIO(jpeg_bytes))
        img = img.convert("RGB")
        arr = np.array(img)

        frame = VideoFrame.from_ndarray(arr, format="rgb24")
        frame.pts = int(pts * 90000)
        frame.time_base = Fraction(1, 90000)

        self._frame_count += 1
        if self._frame_count % 30 == 1:
            logger.info(f"frame decoded pts={int(pts * 90000)} img_size={img.size}")

        return frame


class BrowserStreamConnection:

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.pc: RTCPeerConnection | None = None
        self.track: PlaywrightScreencastTrack | None = None
        self._page = None

    async def start(self):
        page = get_manager().page()
        if not page:
            return False
        self._page = page
        get_manager().set_screencast_connection(self)

        self.pc = RTCPeerConnection()
        self.track = PlaywrightScreencastTrack()
        self.pc.addTrack(self.track)

        screencast = page.screencast
        try:
            await screencast.stop()
        except Exception:
            pass
        track = self.track
        assert track is not None
        await screencast.start(
            on_frame=lambda f: track.add_frame(f["data"]),
            size={"width": 1280, "height": 720},
            quality=80,
        )
        logger.info(f"screencast started size=1280x720 quality=80")

        @self.pc.on("iceconnectionstatechange")
        async def _on_ice_state():
            assert self.pc is not None
            logger.warning(f"ICE state={self.pc.iceConnectionState}")
            if self.pc.iceConnectionState == "failed":
                await self.stop()

        return True

    async def ensure_screencast_active(self):
        if not self._page or not self.track:
            return
        logger.info("screencast reattach after navigation")
        try:
            await self._page.screencast.stop()
        except Exception:
            pass
        try:
            await self._page.screencast.start(
                on_frame=lambda f: self.track.add_frame(f["data"]),  # type: ignore[union-attr]
                size={"width": 1280, "height": 720},
                quality=80,
            )
            logger.info("screencast reattached after navigation")
        except Exception as e:
            logger.warning(f"screencast reattach failed: {e}")

    async def negotiate(self):
        assert self.pc is not None
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        await self.websocket.send_text(json.dumps({
            "type": "offer",
            "sdp": self.pc.localDescription.sdp,
        }))

    async def handle_answer(self, sdp: str):
        assert self.pc is not None
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type="answer")
        )

    async def handle_input(self, msg: dict):
        if not self._page:
            return

        msg_type = msg.get("type")

        if msg_type == "mouse_click":
            x = msg["x"]
            y = msg["y"]
            vw = msg["vw"]
            vh = msg["vh"]
            logger.info(f"HUMAN_INPUT type=mouse_click x={x} y={y} vw={vw} vh={vh} page_url={self._page.url if self._page else 'N/A'}")
            actual_w = await self._page.evaluate("window.innerWidth")
            actual_h = await self._page.evaluate("window.innerHeight")
            actual_x = (x / vw) * actual_w
            actual_y = (y / vh) * actual_h
            logger.info(f"PLAYWRIGHT_CLICK x={actual_x} y={actual_y} viewport=({actual_w}x{actual_h})")
            await self._page.mouse.move(actual_x, actual_y, steps=5)
            await self._page.mouse.click(actual_x, actual_y)

        elif msg_type == "mouse_move":
            x = msg["x"]
            y = msg["y"]
            vw = msg["vw"]
            vh = msg["vh"]
            logger.info(f"HUMAN_INPUT type=mouse_move x={x} y={y} vw={vw} vh={vh}")
            actual_w = await self._page.evaluate("window.innerWidth")
            actual_h = await self._page.evaluate("window.innerHeight")
            actual_x = (x / vw) * actual_w
            actual_y = (y / vh) * actual_h
            await self._page.mouse.move(actual_x, actual_y, steps=3)

        elif msg_type == "key_press":
            key = msg["key"]
            logger.info(f"input received type=key_press key={key}")
            await self._page.keyboard.press(key)

        elif msg_type == "scroll":
            delta = msg.get("deltaY", 0)
            logger.info(f"input received type=scroll deltaY={delta}")
            await self._page.evaluate(f"window.scrollBy(0, {delta})")

        elif msg_type == "type_text":
            text = msg["text"]
            logger.info(f"input received type=type_text")
            await self._page.keyboard.type(text)

    async def stop(self):
        if self.track:
            self.track.stop()
        if self.pc:
            await self.pc.close()
        if self._page:
            try:
                await self._page.screencast.stop()
            except Exception:
                pass

    async def close(self):
        await self.stop()
        get_manager().set_screencast_connection(None)


@router.websocket("/ws/browser")
async def browser_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("websocket connected")

    conn = BrowserStreamConnection(websocket)
    if not await conn.start():
        await websocket.close(code=1011, reason="Browser not launched")
        return

    try:
        await conn.negotiate()

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30
                )
            except asyncio.TimeoutError:
                continue

            msg = json.loads(data)

            if msg["type"] == "answer":
                await conn.handle_answer(msg["sdp"])

            elif msg["type"] in (
                "mouse_click", "mouse_move", "key_press", "scroll", "type_text"
            ):
                takeover = get_manager().takeover
                if takeover and takeover.state == "human_control":
                    await conn.handle_input(msg)
                else:
                    state = takeover.state.value if takeover else "unknown"
                    logger.warning(f"input dropped takeover.state={state} expected human_control")

    except WebSocketDisconnect:
        logger.info("websocket disconnected")
    except Exception:
        logger.info("websocket disconnected")
    finally:
        await conn.close()
