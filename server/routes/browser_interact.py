from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage

from server.dependencies import get_config, require_workspace
from server.sessions import get_session_store
from server.sse_format import sse_done, sse_event
from services.chat_service import persist_chat_run

from server.routes.chat import get_orchestrator, remove_orchestrator

router = APIRouter(prefix="/api/browser", tags=["browser_interact"])


class TakeoverCompleteRequest(BaseModel):
    session_id: str
    result: str


class TakeoverCancelRequest(BaseModel):
    session_id: str


class TakeoverEnterControlRequest(BaseModel):
    session_id: str


class InteractRequest(BaseModel):
    action: str
    selector: str = ""
    value: str = ""
    scroll_pixels: int = 0


class InteractByCoordsRequest(BaseModel):
    x: int
    y: int
    viewport_width: int
    viewport_height: int


@router.post("/takeover/complete")
async def complete_human_takeover(body: TakeoverCompleteRequest):
    require_workspace()
    config = get_config()

    orchestrator = get_orchestrator(body.session_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="No active run for this session")

    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    run_collector: dict[str, Any] = {}
    new_messages_collector: list[ModelMessage] = []
    persisted = False

    async def event_callback(event: dict[str, Any]) -> None:
        await event_queue.put(event)

    run_task = asyncio.create_task(
        orchestrator.resume_after_takeover(
            body.result,
            event_callback,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
        )
    )

    async def generate():
        nonlocal run_collector, new_messages_collector, persisted

        try:
            while True:
                if run_task.done() and event_queue.empty():
                    completed = await run_task
                    if completed:
                        persist_chat_run(
                            session_id=body.session_id,
                            new_messages_collector=new_messages_collector,
                            run_collector=run_collector,
                        )
                        remove_orchestrator(body.session_id)
                        persisted = True
                    break

                event = await event_queue.get()
                ev_type = event.get("type", "")

                if ev_type == "new_messages":
                    new_messages_collector.extend(event.get("messages", []))
                    continue

                if ev_type == "metadata":
                    continue

                if ev_type == "run_end":
                    completed = await run_task
                    if completed:
                        persist_chat_run(
                            session_id=body.session_id,
                            new_messages_collector=new_messages_collector,
                            run_collector=run_collector,
                        )
                        remove_orchestrator(body.session_id)
                        persisted = True
                    yield sse_event(ev_type, event)
                    yield sse_done()
                    break

                if ev_type == "human_takeover_request":
                    yield sse_event(ev_type, event)
                    return

                yield sse_event(ev_type, event)
        finally:
            if not persisted and run_task.done():
                try:
                    if run_task.result() and run_collector.get("run_id"):
                        persist_chat_run(
                            session_id=body.session_id,
                            new_messages_collector=new_messages_collector,
                            run_collector=run_collector,
                        )
                        remove_orchestrator(body.session_id)
                except Exception:
                    pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/takeover/enter-human-control")
async def enter_human_control(body: TakeoverEnterControlRequest):
    from browser import get_manager
    mgr = get_manager()
    mgr.takeover.enter_human_control()
    return {"ok": True, "state": mgr.takeover.state, "message": mgr.takeover.message}


@router.post("/takeover/cancel")
async def cancel_takeover(body: TakeoverCancelRequest):
    from browser import get_manager
    mgr = get_manager()
    mgr.takeover.cancel("用户取消接管")
    return {"ok": True}


@router.post("/takeover/show-window")
async def show_takeover_window():
    from browser import get_manager
    mgr = get_manager()
    await mgr.show_window()
    return {"ok": True}


@router.post("/interact")
async def browser_interact(body: InteractRequest):
    from browser import get_manager
    from browser.actions import click, fill, press_key, scroll_by, go_back, go_forward
    from browser.context import navigate as ctx_navigate

    mgr = get_manager()
    if not mgr.is_launched():
        raise HTTPException(400, "Browser not launched")
    page = mgr.page()
    if page is None:
        raise HTTPException(400, "Browser page not available")

    dispatch = {
        "click": lambda: click(page, body.selector),
        "fill": lambda: fill(page, body.selector, body.value),
        "press_key": lambda: press_key(page, body.value),
        "scroll": lambda: scroll_by(page, body.scroll_pixels),
        "navigate": lambda: ctx_navigate(page, body.value),
        "go_back": lambda: go_back(page),
        "go_forward": lambda: go_forward(page),
    }
    fn = dispatch.get(body.action)
    if not fn:
        raise HTTPException(400, f"Unknown action: {body.action}")
    result = await fn()
    return {"ok": True, "action": body.action, "detail": result}


@router.post("/interact/coords")
async def browser_interact_coords(body: InteractByCoordsRequest):
    from browser import get_manager
    mgr = get_manager()
    if not mgr.is_launched():
        raise HTTPException(400, "Browser not launched")
    page = mgr.page()
    if page is None:
        raise HTTPException(400, "Browser page not available")
    vw = await page.evaluate("window.innerWidth")
    vh = await page.evaluate("window.innerHeight")
    actual_x = (body.x / body.viewport_width) * vw
    actual_y = (body.y / body.viewport_height) * vh
    await page.mouse.click(actual_x, actual_y)
    return {"ok": True}
