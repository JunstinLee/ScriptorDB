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
from browser.takeover import HumanTakeoverState
from logging_setup import get_logger

logger = get_logger("browser_stream")

router = APIRouter(prefix="/api", tags=["browser_stream"])
_screencast_lock = asyncio.Lock()
_browser_recovery_lock = asyncio.Lock()


def _is_target_closed_error(error: Exception) -> bool:
    return (
        type(error).__name__ == "TargetClosedError"
        or "Target page, context or browser has been closed" in str(error)
    )


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
        self.target_closed = False

    async def start(self):
        self.target_closed = False
        manager = get_manager()
        page = manager.page()
        if not page:
            logger.warning("browser stream start skipped: browser page unavailable")
            return False
        self._page = page

        self.pc = RTCPeerConnection()
        self.track = PlaywrightScreencastTrack()
        self.pc.addTrack(self.track)

        screencast = page.screencast
        try:
            async with _screencast_lock:
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
        except Exception as e:
            self.target_closed = _is_target_closed_error(e)
            if self.target_closed:
                manager.mark_browser_unavailable()
            logger.warning(f"screencast start failed: {e}")
            await self.close()
            return False

        manager.set_screencast_connection(self)
        logger.info(f"screencast started size=1280x720 quality=80")

        @self.pc.on("iceconnectionstatechange")
        async def _on_ice_state():
            assert self.pc is not None
            logger.warning(f"ICE state={self.pc.iceConnectionState}")
            if self.pc.iceConnectionState == "failed":
                await self.stop()

        return True

    async def ensure_screencast_active(self):
        manager = get_manager()
        if not self.track or not manager.is_screencast_connection(self):
            return
        page = manager.page()
        if not page:
            await self.close()
            return
        self._page = page
        logger.info("screencast reattach after navigation")
        target_closed = False
        try:
            async with _screencast_lock:
                if not manager.is_screencast_connection(self):
                    return
                try:
                    await page.screencast.stop()
                except Exception:
                    pass
                await page.screencast.start(
                    on_frame=lambda f: self.track.add_frame(f["data"]),  # type: ignore[union-attr]
                    size={"width": 1280, "height": 720},
                    quality=80,
                )
            logger.info("screencast reattached after navigation")
        except Exception as e:
            target_closed = _is_target_closed_error(e)
            if target_closed:
                manager.mark_browser_unavailable()
            logger.warning(f"screencast reattach failed: {e}")
        if target_closed:
            await self.close()

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
        # 只读预览策略：视频流不接收鼠标/键盘/滚轮输入，真实 Chrome 窗口是唯一操作入口。
        msg_type = msg.get("type")
        logger.warning(f"video input unsupported, dropped type={msg_type}")

    async def stop(self):
        async with _screencast_lock:
            manager = get_manager()
            owns_screencast = manager.is_screencast_connection(self)

            if self.track:
                self.track.stop()
                self.track = None
            if self.pc:
                pc = self.pc
                await pc.close()
                if self.pc is pc:
                    self.pc = None
            if owns_screencast and self._page:
                try:
                    await self._page.screencast.stop()
                except Exception:
                    pass
            self._page = None

    async def close(self):
        await self.stop()
        get_manager().clear_screencast_connection(self)


async def _recover_browser_target() -> bool:
    """Perform one serialized visible-browser recovery after a target closes."""
    manager = get_manager()
    async with _browser_recovery_lock:
        if manager.page() is not None:
            return True

        result = await manager.launch()
        recovered = manager.page() is not None
        logger.warning(
            f"browser stream recovery launch result={result} recovered={recovered}"
        )
        return recovered


@router.websocket("/ws/browser")
async def browser_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("websocket connected")

    conn = BrowserStreamConnection(websocket)
    try:
        started = await conn.start()
        if not started and conn.target_closed:
            logger.warning("browser stream target closed during startup; attempting recovery")
            if await _recover_browser_target():
                started = await conn.start()

        if not started:
            logger.warning("browser stream unavailable; closing websocket")
            await websocket.close(code=1011, reason="Browser target unavailable")
            return

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
                if takeover and takeover.state == HumanTakeoverState.HUMAN_CONTROL:
                    logger.info("video input rejected during human_control (use the real Chrome window)")
                else:
                    state = takeover.state.value if takeover else "unknown"
                    logger.warning(f"input rejected takeover.state={state}")

    except WebSocketDisconnect:
        logger.info("websocket disconnected")
    except Exception as e:
        logger.warning(f"browser websocket failed: {e}")
    finally:
        await conn.close()
