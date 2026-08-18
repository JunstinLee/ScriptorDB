from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.dependencies import get_config, require_workspace
from api.routes.chat import get_orchestrator, remove_orchestrator

router = APIRouter(prefix="/api/browser", tags=["browser_interact"])


class TakeoverCompleteRequest(BaseModel):
    session_id: str
    result: str
    run_id: str = ""


class TakeoverCancelRequest(BaseModel):
    session_id: str
    run_id: str = ""


class TakeoverEnterControlRequest(BaseModel):
    session_id: str


class InteractRequest(BaseModel):
    action: str
    selector: str = ""
    value: str = ""
    scroll_pixels: int = 0
    # 筛选动作字段（action 为 select/input/toggle/set_range/date_range 时使用）
    target: str = ""
    values: str = ""
    submit: bool = True


class InteractByCoordsRequest(BaseModel):
    x: int
    y: int
    viewport_width: int
    viewport_height: int


@router.post("/takeover/complete")
async def complete_human_takeover(body: TakeoverCompleteRequest):
    require_workspace()
    get_config()

    orchestrator = get_orchestrator(body.session_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="No active run for this session")
    if body.run_id and orchestrator.run_id != body.run_id:
        raise HTTPException(
            status_code=409,
            detail="Run mismatch: the takeover belongs to a different run",
        )

    # 不重启 run：仅唤醒原 run 内部挂起的 resume_event，返回 JSON；
    # 后续事件继续由原 chat SSE 流推送。
    result = orchestrator.resume_takeover(body.run_id, body.result)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "Cannot resume takeover"))
    return result


@router.post("/takeover/enter-human-control")
async def enter_human_control(body: TakeoverEnterControlRequest):
    from browser import get_manager
    mgr = get_manager()
    mgr.cancel_idle_close()
    mgr.takeover.enter_human_control()
    return {"ok": True, "state": mgr.takeover.state, "message": mgr.takeover.message}


@router.post("/takeover/cancel")
async def cancel_takeover(body: TakeoverCancelRequest):
    orchestrator = get_orchestrator(body.session_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="No active takeover for this session")

    result = orchestrator.cancel_takeover(body.run_id, "用户取消接管")
    if not result.get("ok"):
        if result.get("error") == "run_mismatch":
            raise HTTPException(
                status_code=409,
                detail="Run mismatch: the takeover belongs to a different run",
            )
        raise HTTPException(status_code=409, detail=result.get("error", "Cannot cancel takeover"))

    remove_orchestrator(body.session_id)
    return result


@router.post("/takeover/show-window")
async def show_takeover_window():
    from browser import get_manager
    mgr = get_manager()
    mgr.cancel_idle_close()
    await mgr.show_window()
    return {"ok": True}


@router.post("/interact")
async def browser_interact(body: InteractRequest):
    from browser import get_manager
    from browser.actions import click, fill, press_key, scroll_by, go_back, go_forward
    from browser.context import navigate as ctx_navigate
    from tools.browser_tools.filter_apply import FILTER_ACTIONS, execute_filter_action

    mgr = get_manager()
    mgr.cancel_idle_close()
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
    # 筛选动作：与 browser_apply_filter 共用同一执行实现，行为一致
    for _act in FILTER_ACTIONS:
        dispatch[_act] = lambda _a=_act: execute_filter_action(
            page, _a, body.target, body.value, body.values, body.submit
        )
    fn = dispatch.get(body.action)
    if not fn:
        raise HTTPException(400, f"Unknown action: {body.action}")
    result = await fn()
    return {"ok": True, "action": body.action, "detail": result}


@router.post("/interact/coords")
async def browser_interact_coords(body: InteractByCoordsRequest):
    from browser import get_manager
    mgr = get_manager()
    mgr.cancel_idle_close()
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


@router.post("/close")
async def close_browser():
    from browser import get_manager
    require_workspace()
    mgr = get_manager()
    if not mgr.is_launched():
        return {"ok": True, "detail": "Browser not running"}
    await mgr.close()
    return {"ok": True, "detail": "Browser closed"}
