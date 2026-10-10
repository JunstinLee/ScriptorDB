"""元素引用（ref）的执行期校验。

``browser/refs.py`` 只负责铸造 / 解析 :class:`RefRecord`;「这个 ref 是否仍指向
同一元素」的判定属于浏览器层,集中在此模块。工具层只消费
:func:`_resolve_ref_target` 的结果,不再承担签名比对与 stale 判定。
"""

from __future__ import annotations

import asyncio

from browser.refs import invalidate_ref, resolve_ref
from core.logging_setup import get_logger
from schemas import ToolErrorInfo, ToolResult

logger = get_logger("browser.ref_verify")

_REF_RESOLVE_TIMEOUT_MS = 1500

_REASON_UNKNOWN = "unknown"
_REASON_PAGE_CLOSED = "page_closed"
_REASON_URL_CHANGED = "url_changed"
_REASON_ELEMENT_MISSING = "element_missing"
_REASON_SIGNATURE_MISMATCH = "signature_mismatch"

# 不保身份的定位器种类：它们本就可能解析回别的节点，硬身份冲突不能据此判 stale。
_WEAK_LOCATOR_KINDS = {"text", "path"}

# 唯一性强的定位符种类：冲突时先重采样签名、再按「选择器仍唯一可解析」放行，
# 不直接判 stale（动态重渲染页面里角色/属性抖动会误伤）。
_STRONG_UNIQUE_LOCATOR_KINDS = {"id", "data"}

# 强唯一定位符冲突时重采样签名的窗口：tries 次、每次间隔 delay 秒，取出现次数最多者。
_SIGNATURE_RESAMPLE_TRIES = 3
_SIGNATURE_RESAMPLE_DELAY = 0.05


def _stale_ref(ref: str, reason: str = "") -> ToolResult:
    logger.info("ref stale: %s (%s)", ref, reason or _REASON_UNKNOWN)
    detail = f" ({reason})" if reason else ""
    return ToolResult(
        success=False,
        error=ToolErrorInfo(
            category="stale_ref",
            message=(
                f"Ref '{ref}' is stale{detail}. The page or element changed since the "
                "ref was minted. Call browser_find again to get a fresh ref."
            ),
        ),
    )


def _split_signature(sig: str) -> tuple[str, str]:
    """把 ``[tag, role, aria, text]`` 签名拆成 (结构身份, 可变信号)。

    结构身份只取 tag：标签名由标记本身决定，最稳定。role 会被状态切换/渲染
    改写（例如同一节点在 clickable/render 之间切换 role），aria-label 与
    textContent 在 SPA 里每轮渲染都可能被改写，放进结构身份都会把「同一个
    元素」误判成 stale，故一律降级为可变信号。段数不等于 4 视为不可判，
    返回 ``("", "")``，由调用方按「算不出」处理。
    """
    parts = (sig or "").split("\u0001")
    if len(parts) != 4:
        return "", ""
    return parts[0], "\u0001".join(parts[1:])


async def _element_signature(handle) -> str | None:
    from browser.locate_script import ELEMENT_SIGNATURE_JS

    try:
        return str(await handle.evaluate(ELEMENT_SIGNATURE_JS))
    except Exception:
        return None


async def _resample_signature(handle) -> str | None:
    """短窗口内多次取签名，取出现次数最多者（动态重渲染下单次采样会抖动）。"""
    samples: list[str] = []
    for _ in range(_SIGNATURE_RESAMPLE_TRIES):
        sig = await _element_signature(handle)
        if sig:
            samples.append(sig)
        await asyncio.sleep(_SIGNATURE_RESAMPLE_DELAY)
    if not samples:
        return None
    return max(set(samples), key=samples.count)


async def _selector_unique(page, selector: str) -> bool:
    """选择器是否仍唯一可解析（强唯一定位符按此判定元素未变）。"""
    try:
        return len(await page.query_selector_all(selector)) == 1
    except Exception:
        return False


async def _resolve_ref_target(manager, ref: str):
    """把 ref 解析回 (page, locator)，并证明它仍指向同一元素。

    先比对铸造时 URL（点击触发的整页跳转不经失效挂点，Page 对象跨导航不变，
    只比签名会让同 locator 同签名的元素被静默误命中），再等元素挂载后分级比对
    签名（硬身份只取 tag）：硬身份一致即命中；软信号抖动、签名算不出都记
    ``unverified`` 放行；硬身份冲突时——弱定位器失效后放行；强唯一定位符
    （id / data）先重采样签名，仍冲突且选择器已不唯一才 ``stale_ref``。
    """
    record = resolve_ref(ref)
    if record is None:
        return _stale_ref(ref, _REASON_UNKNOWN)
    page = record.page
    if page is None or page.is_closed():
        return _stale_ref(ref, _REASON_PAGE_CLOSED)
    if (page.url or "") != record.page_url:
        return _stale_ref(ref, _REASON_URL_CHANGED)
    try:
        await page.wait_for_selector(record.locator, timeout=_REF_RESOLVE_TIMEOUT_MS)
    except Exception:
        return _stale_ref(ref, _REASON_ELEMENT_MISSING)
    try:
        handle = await page.query_selector(record.locator)
    except Exception:
        handle = None
    if handle is None:
        return _stale_ref(ref, _REASON_ELEMENT_MISSING)
    signature = await _element_signature(handle)
    if signature is None:
        logger.info("ref reuse unverified: %s (signature unavailable)", ref)
        return page, record.locator
    hard, soft = _split_signature(signature)
    rec_hard, rec_soft = _split_signature(record.signature)
    if not hard or not rec_hard:
        logger.info("ref reuse unverified: %s (signature unavailable)", ref)
        return page, record.locator
    if hard == rec_hard:
        if soft != rec_soft:
            logger.info("ref reuse unverified: %s (soft text drift)", ref)
        return page, record.locator
    if record.locator_kind in _WEAK_LOCATOR_KINDS:
        logger.info(
            "ref reuse unverified: %s (weak locator %s)", ref, record.locator_kind
        )
        invalidate_ref(ref)
        return page, record.locator
    if record.locator_kind in _STRONG_UNIQUE_LOCATOR_KINDS:
        # 唯一性强：先短窗口重采样，取到稳定签名后再比一次硬身份。
        stable = await _resample_signature(handle)
        if stable is not None:
            resampled_hard, _ = _split_signature(stable)
            if resampled_hard and resampled_hard == rec_hard:
                logger.info(
                    "ref reuse unverified: %s (strong locator %s, resampled match)",
                    ref, record.locator_kind,
                )
                return page, record.locator
        # 仍冲突但选择器唯一可解析：按「定位符保身份」放行。
        if await _selector_unique(page, record.locator):
            logger.info(
                "ref reuse unverified: %s (strong locator %s, selector still unique)",
                ref, record.locator_kind,
            )
            return page, record.locator
    return _stale_ref(ref, _REASON_SIGNATURE_MISMATCH)
