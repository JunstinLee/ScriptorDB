#!/usr/bin/env python3
"""
WebRTC Browser Stream Diagnostic — 诊断 BrowserViewportStream 视频流为啥空白。

用法:
    uv run python tests/test_browser_stream_diag.py              # 纯 API 层 (Layer 0-3)
    uv run python tests/test_browser_stream_diag.py --frames 3   # 收 3 帧然后退出

要求:
    - 后端运行在 localhost:8000
    - Playwright 浏览器已启动 (agent 调过 browser_launch)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack

os.environ.setdefault("no_proxy", "localhost,127.0.0.1,::1")

BACKEND_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/api/ws/browser"

# ---------------------------------------------------------------------------
# ANSI
# ---------------------------------------------------------------------------

_G = "\033[92m"
_R = "\033[91m"
_Y = "\033[93m"
_C = "\033[96m"
_B = "\033[1m"
_N = "\033[0m"

OK = _G + "PASS" + _N
FAIL = _R + "FAIL" + _N
SKIP = _Y + "SKIP" + _N
WARN = _Y + "WARN" + _N


def _tag(ok_: bool) -> str:
    return OK if ok_ else FAIL


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    layer: int
    title: str
    ok: bool = True
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------


class BrowserStreamDiagnostic:
    def __init__(self, frame_count: int = 0, timeout: int = 10):
        self._frame_count = frame_count
        self._timeout = timeout
        self._results: list[CheckResult] = []
        self._browser_state: dict[str, Any] = {}
        self._received_frames = 0
        self._frame_sizes: list[int] = []

    # ------------------------------------------------------------------
    # Layer 0 — Backend reachable + workspace active
    # ------------------------------------------------------------------

    async def check_layer_0(self, client: httpx.AsyncClient) -> bool:
        try:
            resp = await client.get(f"{BACKEND_URL}/api/browser/state")
        except Exception as e:
            self._results.append(CheckResult(
                layer=0, title="Browser State Endpoint", ok=False,
                message=f"Cannot reach {BACKEND_URL}. Backend running?\n        {e}",
            ))
            return False

        if resp.status_code == 409:
            self._results.append(CheckResult(
                layer=0, title="Workspace Active", ok=False,
                message="HTTP 409 — no active workspace. Switch one first.",
            ))
            return False

        if resp.status_code != 200:
            self._results.append(CheckResult(
                layer=0, title="Backend Health", ok=False,
                message=f"HTTP {resp.status_code}",
            ))
            return False

        state = resp.json()
        self._browser_state = state
        self._results.append(CheckResult(
            layer=0, title="Backend Reachable",
            ok=True,
            message=f"{BACKEND_URL} → HTTP 200",
            data={"workspace_ok": True},
        ))
        return True

    # ------------------------------------------------------------------
    # Layer 1 — Browser launch state
    # ------------------------------------------------------------------

    async def check_layer_1(self) -> bool:
        launched = self._browser_state.get("launched", False)
        url = self._browser_state.get("url", "")
        title = self._browser_state.get("title", "")

        detail = f"launched={launched}, url={url}, title={(title or '(empty)')[:60]}"
        self._results.append(CheckResult(
            layer=1, title="Browser Launched",
            ok=launched,
            message=detail,
            data={"launched": launched, "url": url, "title": title},
        ))
        return launched

    # ------------------------------------------------------------------
    # Layer 2 — WebSocket connection + SDP handshake
    # ------------------------------------------------------------------

    async def check_layer_2(self) -> dict[str, Any]:
        """Returns {"pc": pc, "ws": ws} if successful, or {} if failed."""
        try:
            ws = await asyncio.wait_for(
                websockets.connect(WS_URL, ping_interval=20),
                timeout=5,
            )
        except asyncio.TimeoutError:
            self._results.append(CheckResult(
                layer=2, title="WebSocket Connect", ok=False,
                message=f"Timeout connecting to {WS_URL}. Backend blocking?",
            ))
            return {}
        except Exception as e:
            self._results.append(CheckResult(
                layer=2, title="WebSocket Connect", ok=False,
                message=f"Failed to connect: {e}",
            ))
            return {}

        self._results.append(CheckResult(
            layer=2, title="WebSocket Connect",
            ok=True,
            message=f"Connected to {WS_URL}",
        ))

        pc = RTCPeerConnection()
        ice_states: list[str] = []
        signaling_states: list[str] = []
        connection_states: list[str] = []

        @pc.on("iceconnectionstatechange")
        async def _on_ice():
            s = pc.iceConnectionState
            ice_states.append(s)
            print(f"        [ICE] {s}")

        @pc.on("signalingstatechange")
        async def _on_sig():
            s = pc.signalingState
            signaling_states.append(s)
            print(f"        [SIG] {s}")

        @pc.on("connectionstatechange")
        async def _on_conn():
            s = pc.connectionState
            connection_states.append(s)
            print(f"        [CON] {s}")

        @pc.on("track")
        def _on_track(track: MediaStreamTrack):
            print(f"        [TRACK] received: kind={track.kind}, id={track.id}")
            if track.kind == "video" and self._frame_count > 0:
                asyncio.ensure_future(self._recv_frames(track))

        # Wait for SDP offer from server
        offer_received = False
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)
            if msg.get("type") != "offer":
                self._results.append(CheckResult(
                    layer=2, title="SDP Offer Received", ok=False,
                    message=f"Expected 'offer', got: {json.dumps(msg, indent=2)[:200]}",
                ))
                await ws.close()
                return {}
            offer_received = True
            offer_sdp_len = len(msg.get("sdp", ""))

            self._results.append(CheckResult(
                layer=2, title="SDP Offer Received",
                ok=True,
                message=f"Received offer ({offer_sdp_len} bytes SDP)",
                data={"sdp_len": offer_sdp_len},
            ))

            # Set remote description and create answer
            desc = RTCSessionDescription(sdp=msg["sdp"], type="offer")
            await pc.setRemoteDescription(desc)
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            # Send answer back
            await ws.send(json.dumps({
                "type": "answer",
                "sdp": pc.localDescription.sdp,
            }))
            answer_sdp_len = len(pc.localDescription.sdp)

            self._results.append(CheckResult(
                layer=2, title="SDP Answer Sent",
                ok=True,
                message=f"Sent answer ({answer_sdp_len} bytes SDP)",
                data={"answer_sdp_len": answer_sdp_len},
            ))

        except asyncio.TimeoutError:
            self._results.append(CheckResult(
                layer=2, title="SDP Offer Received", ok=False,
                message="Timeout waiting for SDP offer. Server might not be running Playwright screencast.",
            ))
            await ws.close()
            await pc.close()
            return {}
        except Exception as e:
            self._results.append(CheckResult(
                layer=2, title="SDP Handshake", ok=False,
                message=f"Error: {e}",
            ))
            await ws.close()
            await pc.close()
            return {}

        # Wait a moment for ICE candidate exchange
        await asyncio.sleep(1)

        # Exchange ICE candidates
        ice_sent = 0
        ice_received = 0

        @pc.on("icecandidate")
        async def _on_ice_candidate(candidate):
            nonlocal ice_sent
            if candidate:
                ice_sent += 1
                await ws.send(json.dumps({
                    "type": "ice_candidate",
                    "candidate": {
                        "candidate": candidate.candidate,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                        "sdpMid": candidate.sdpMid,
                    },
                }))

        # Receive ICE candidates from server (non-blocking for a bit)
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
                msg = json.loads(raw)
                if msg.get("type") == "ice_candidate" and "candidate" in msg:
                    if msg["candidate"] and msg["candidate"].get("candidate"):
                        ice_received += 1
                        try:
                            await pc.addIceCandidate(msg["candidate"])
                        except Exception:
                            pass
        except asyncio.TimeoutError:
            pass

        self._results.append(CheckResult(
            layer=2, title="ICE Candidates",
            ok=True,
            message=f"Sent {ice_sent}, received {ice_received}",
            data={"sent": ice_sent, "received": ice_received},
        ))

        # Wait for ICE to settle
        await asyncio.sleep(3)

        ice_final = pc.iceConnectionState
        conn_final = pc.connectionState

        ice_ok = ice_final == "connected" or ice_final == "completed"
        conn_ok = conn_final == "connected"

        status_line = f"ICE={ice_final}   connection={conn_final}  "
        status_line += f"states: ICE {'→'.join(ice_states)}, SIG {'→'.join(signaling_states)}, CON {'→'.join(connection_states)}"

        self._results.append(CheckResult(
            layer=2, title="WebRTC Connection State",
            ok=ice_ok or conn_ok,
            message=status_line,
            data={
                "ice_state": ice_final,
                "connection_state": conn_final,
                "ice_states": ice_states,
                "signaling_states": signaling_states,
                "connection_states": connection_states,
            },
        ))

        # If we want to receive frames, wait for them
        if self._frame_count > 0 and (ice_ok or conn_ok):
            start = time.time()
            while self._received_frames < self._frame_count:
                if time.time() - start > 15:
                    break
                await asyncio.sleep(0.1)

            self._results.append(CheckResult(
                layer=2, title=f"Video Frames (wanted {self._frame_count})",
                ok=self._received_frames >= self._frame_count,
                message=f"Received {self._received_frames} frames in {time.time() - start:.1f}s. "
                        f"Sizes: {self._frame_sizes[:5]}",
                data={
                    "received": self._received_frames,
                    "wanted": self._frame_count,
                    "sizes": self._frame_sizes,
                },
            ))

        return {"pc": pc, "ws": ws}

    async def _recv_frames(self, track: MediaStreamTrack):
        while self._received_frames < self._frame_count:
            try:
                frame = await track.recv()
                self._received_frames += 1
                size = 1
                self._frame_sizes.append(size)
            except Exception:
                break

    # ------------------------------------------------------------------
    # Layer 3 — Browser action history
    # ------------------------------------------------------------------

    async def check_layer_3(self) -> None:
        actions = self._browser_state.get("actions", [])
        history = self._browser_state.get("history", [])

        lines = [f"Actions recorded: {len(actions)}, nav entries: {len(history)}"]
        for a in actions[-5:]:
            lines.append(f"  {a.get('tool')} → {a.get('detail', '')}")

        self._results.append(CheckResult(
            layer=3, title="Browser Activity",
            ok=True,
            message="\n".join(lines),
            data={"action_count": len(actions), "history_count": len(history)},
        ))

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def run(self) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            if not await self.check_layer_0(client):
                self.print_report()
                return

            if not await self.check_layer_1():
                self.print_report()
                return

            await self.check_layer_3()

            conns = await self.check_layer_2()

        if conns:
            await conns["ws"].close()
            await conns["pc"].close()

        self.print_report()

    def print_report(self) -> None:
        print()
        print(f"{_B}{'=' * 68}{_N}")
        print(f"  {_B}WebRTC Browser Stream Diagnostic{_N}")
        print(f"{_B}{'=' * 68}{_N}")
        print(f"  Time:       {datetime.now().isoformat()[:19]}")
        print(f"  Backend:    {BACKEND_URL}")
        print(f"  WebSocket:  {WS_URL}")
        print()

        for r in self._results:
            tag = SKIP if r.skipped else _tag(r.ok)
            print(f"  [{tag}] L{r.layer}  {r.title}")
            for line in r.message.split("\n"):
                print(f"        {line}")
            print()

        print(f"  {_B}Summary{_N}")
        print(f"  {'─' * 40}")
        all_ok = all(r.ok for r in self._results)
        if all_ok:
            print(f"  {_G}All checks passed.{_N}")
        else:
            failed = [r for r in self._results if not r.ok]
            for r in failed:
                print(f"  L{r.layer} FAIL: {r.message.split(chr(10))[0]}")

        print(f"\n{_B}{'=' * 68}{_N}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(
        description="WebRTC Browser Stream Diagnostic — 诊断 BrowserViewportStream 视频空白",
    )
    parser.add_argument(
        "--frames", type=int, default=0,
        help="尝试接收 N 帧视频后退出 (default: 0, 不等待帧)",
    )
    parser.add_argument(
        "--timeout", type=int, default=10,
        help="HTTP 超时秒数 (default: 10)",
    )
    args = parser.parse_args()

    diag = BrowserStreamDiagnostic(frame_count=args.frames, timeout=args.timeout)
    await diag.run()


if __name__ == "__main__":
    asyncio.run(main())
